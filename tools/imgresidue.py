"""imgresidue — 배경 글씨(글자를 지운 배경) 결과에 일본어 잉크 찌꺼기가 남았는지 상자마다 잰다. numpy·opencv(cv2) 를 쓴다.

imgcodex 가 --erase-only 꾸러미를 검사할 때 부른다.

잉크 찾기: 상자(일본어가 있는 대략의 네모) 둘레의 바탕을 추정하고, 바탕과 thr 넘게 다른 화소를 글씨로 본다
(몸통·외곽선·그림자·번짐). 상자 밖으로 넘친 글자도 상자 안 글씨와 이어져 있고 글자만 한 크기면 잡는다.
길게 이어진 줄·테두리는 빼고, kind=keep 상자도 뺀다.
찌꺼기: 결과 그림에서 잉크 찾기를 한 번 더 돌려 상자마다 남은 잉크의 가장 큰 덩어리(화소 수)를 잰다.
limit(기본 12) 이하면 「통과」, 넘으면 「사람 확인」. 둘레가 투명한 상자는 다 비었으면 「통과」, 아니면 「건너뜀」.

기준 12 는 표본 5장으로 정한 잠정값이다: 깨끗한 상자 0~6화소, 글자 유령이 남은 상자 36~1468, 명판 테두리가 걸친 상자 232~526.
무늬·테두리가 상자 안에 있으면 깨끗해도 「사람 확인」으로 간다(안전한 쪽으로 틀린다).
"""
import csv
from pathlib import Path

import numpy as np


def read_boxes(path, classes):
    files = sorted(Path(path).glob('*.csv')) if Path(path).is_dir() else [Path(path)]
    out = {}
    for f in files:
        with open(f, encoding='utf-8-sig', newline='') as fh:
            for r in csv.DictReader(fh):
                try:
                    b = tuple(int(float(r[k])) for k in ('x0', 'y0', 'x1', 'y1'))
                except (KeyError, ValueError, TypeError):
                    continue
                kind = (r.get('kind') or 'edit').strip() or 'edit'
                if kind == 'edit' and classes and (r.get('분류') or '').strip() not in classes:
                    continue
                name = Path((r.get('file') or '').strip()).name
                if name:
                    out.setdefault(name, []).append((b, 'keep' if kind == 'keep' else 'edit'))
    return out


def _clip(b, W, H):
    x0, y0, x1, y1 = b
    return max(0, x0), max(0, y0), min(W, x1), min(H, y1)


def _ring(rgba, b, r=2):
    """상자 밖 r 화소 둘레. 상자가 그림을 꽉 채우면 상자 안 가장자리 1화소."""
    H, W = rgba.shape[:2]
    x0, y0, x1, y1 = b
    X0, Y0, X1, Y1 = _clip((x0 - r, y0 - r, x1 + r, y1 + r), W, H)
    m = np.zeros((H, W), bool)
    m[Y0:Y1, X0:X1] = True
    m[y0:y1, x0:x1] = False
    if m.sum() < 4:
        m[y0:y1, x0:x1] = True
        m[y0 + 1:y1 - 1, x0 + 1:x1 - 1] = False
    return rgba[m]


def cells(ink, g, grow):
    """잉크가 걸친 g px 칸 -> grow 칸 넓힘 -> 화소 마스크."""
    H, W = ink.shape
    gh, gw = -(-H // g), -(-W // g)
    p = np.zeros((gh * g, gw * g), bool)
    p[:H, :W] = ink
    c = p.reshape(gh, g, gw, g).any(axis=(1, 3))
    for _ in range(grow):
        n = c.copy()
        n[1:] |= c[:-1]; n[:-1] |= c[1:]
        n[:, 1:] |= c[:, :-1]; n[:, :-1] |= c[:, 1:]
        n[1:, 1:] |= c[:-1, :-1]; n[:-1, :-1] |= c[1:, 1:]
        n[1:, :-1] |= c[:-1, 1:]; n[:-1, 1:] |= c[1:, :-1]
        c = n
    return np.repeat(np.repeat(c, g, 0), g, 1)[:H, :W]


def _ring_transparent(rgba, b):
    r = _ring(rgba, b, 3)
    return len(r) > 0 and (r[:, 3] < 16).mean() > 0.5


def build_masks(rgba, boxes, g, grow, thr, whole, clear=False, k=15, reach=16, maxc=28):
    """-> (투명으로 비울 화소, 바탕으로 채워야 할 화소(글씨 잉크), 건너뛴 투명 바탕 상자 수).

    잉크 찾기: 그림을 회색 위에 합성 -> 중간값 흐림(k)으로 바탕 추정 -> 바탕과 thr 넘게 다른 화소를 1차 잉크로 보고
    그 자리를 지운(OpenCV inpaint) 바탕과 다시 견준다(굵은 글씨 속까지 잡는다).
    상자 안 잉크는 모두 넣는다. 상자 밖 reach px 안의 잉크는 상자 안 잉크와 이어져 있고 크기가 글자만 할 때(maxc px 이하)만 넣는다
    — 상자를 빠듯하게 잡아 넘친 글자는 잡고, 길게 이어진 줄·테두리 같은 그림은 뺀다.
    둘레가 투명한 상자는 --clear 일 때만 보이는 화소를 투명하게 비운다. 아니면 건너뛴다(글씨 뒤 명판·아이콘을 못 가른다)."""
    import cv2
    H, W = rgba.shape[:2]
    a = rgba[..., 3:4].astype(np.float32) / 255
    comp = (rgba[..., :3] * a + 128 * (1 - a)).round().astype(np.uint8)
    edit = np.zeros((H, W), bool)
    search = np.zeros((H, W), bool)
    keep = np.zeros((H, W), bool)
    clear_ink = np.zeros((H, W), bool)
    skipped = 0
    for b, kind in boxes:
        x0, y0, x1, y1 = _clip(b, W, H)
        if x1 <= x0 or y1 <= y0:
            continue
        if kind == 'keep':
            keep[y0:y1, x0:x1] = True
            continue
        if _ring_transparent(rgba, (x0, y0, x1, y1)):
            if clear:
                clear_ink[y0:y1, x0:x1] |= rgba[y0:y1, x0:x1, 3] >= 16
            else:
                skipped += 1
            continue
        edit[y0:y1, x0:x1] = True
        X0, Y0, X1, Y1 = _clip((x0 - reach, y0 - reach, x1 + reach, y1 + reach), W, H)
        search[Y0:Y1, X0:X1] = True
    if whole:
        ink = edit.copy()
    else:
        def diff(bg):
            return np.sqrt(((comp.astype(np.float32) - bg.astype(np.float32)) ** 2).sum(-1))
        ink1 = (diff(cv2.medianBlur(comp, k)) > thr) & search
        bg2 = cv2.inpaint(comp, cv2.dilate(ink1.astype(np.uint8) * 255, np.ones((3, 3), np.uint8)), 5, cv2.INPAINT_TELEA)
        ink = (diff(bg2) > thr) & search & ~keep
        k5 = np.ones((5, 5), np.uint8)
        inside, outside = ink & edit, ink & ~edit
        near = cv2.dilate(inside.astype(np.uint8), k5) > 0
        n, lab, st, _ = cv2.connectedComponentsWithStats(cv2.dilate(outside.astype(np.uint8), k5), connectivity=8)
        ok = np.zeros(n, bool)
        for i in range(1, n):
            if st[i, 2] <= maxc and st[i, 3] <= maxc and near[lab == i].any():
                ok[i] = True
        ink = inside | (outside & ok[lab])
    mt = cells(clear_ink, g, grow) & ~keep
    ml = cells(ink, g, grow) & ~keep & ~mt & (rgba[..., 3] >= 16)
    return mt, ml, skipped


# 채우기 --------------------------------------------------------------------------------

def _blob(m):
    import cv2
    n, _, st, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8), connectivity=8)
    return int(st[1:, 4].max()) if n > 1 else 0


def residue(orig, res, boxes, thr, limit):
    """상자마다 (상자, 지우기 전 잉크, 남은 잉크, 가장 큰 덩어리, 판정). 판정: 통과 · 사람 확인 · 건너뜀(둘레가 투명해 지우지 않은 상자).
    결과 그림에서 잉크 찾기를 넓힘 없이 다시 돌린다. 투명해진 화소는 찌꺼기가 아니다."""
    H, W = orig.shape[:2]
    before = build_masks(orig, boxes, 1, 0, thr, False)[1]
    after = build_masks(res, boxes, 1, 0, thr, False)[1] & (res[..., 3] >= 16)
    out = []
    for b, kind in boxes:
        if kind == 'keep':
            continue
        x0, y0, x1, y1 = _clip(b, W, H)
        if x1 <= x0 or y1 <= y0:
            continue
        if _ring_transparent(orig, (x0, y0, x1, y1)):
            cleared = not (res[y0:y1, x0:x1, 3] >= 16).any()
            out.append(((x0, y0, x1, y1), 0, 0, 0, '통과' if cleared else '건너뜀'))
            continue
        m = after[y0:y1, x0:x1]
        big = _blob(m)
        out.append(((x0, y0, x1, y1), int(before[y0:y1, x0:x1].sum()), int(m.sum()), big, '통과' if big <= limit else '사람 확인'))
    return out
