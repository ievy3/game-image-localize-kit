"""그림 글자 상자 밖 변경 지도 — 원본 · 결과 · 상자 CSV 를 화소로 견준다. 1.6.0 부터 참고용: 합격·삽입 조건이 아니다
(사용자 결정 2026-11-10 — 일본어는 칸 밖으로 넘친 획까지 지운다. 바뀐 곳이 일본어 자리인지는 눈으로 img.py imgview).

    img.py imgbox --orig src --result <결과 폴더> --boxes grids
                  [--visible VISIBLE.csv | --visible-rect 0,0,480,272]
                  [--transparent auto|alpha|rgb:128,128,128|none] [--out reports/IMGBOX.csv]

규칙(IMAGE_RULES.md):
    빨간 상자(kind=edit) 안은 투명 칸까지 무엇이든 고쳐도 된다. 상자 밖 · 화면 밖 · 유지 상자(kind=keep) 안은 변경 0.
상자 CSV 열: file, x0, y0, x1, y1[, kind] — x1·y1 은 들어가지 않는다(폭 = x1 - x0). kind 를 비우면 edit. 다른 열은 무시.
    file 은 결과 폴더 안의 상대 경로(또는 파일 이름). 상자가 없는 그림은 모든 변경이 상자 밖이다.
화면 범위 CSV 열: file, x0, y0, x1, y1 — 화면에 보이는 칸. 없는 그림은 --visible-rect, 그것도 없으면 그림 전체.
투명 칸: auto = 원본에 알파가 있으면 알파 0 인 화소, 없으면 검사 안 함. rgb:R,G,B = 원본에서 그 색인 화소(투명 표시색).
판정: PASS = 크기 같음 · 상자 밖 0 · 화면 밖 0 · 유지 상자 0. 하나라도 FAIL 이면 끝 코드 1.
상자 안 투명 칸이 바뀐 그림은 PASS 여도 「알파 확인」을 단다 — 알파를 다시 만드는 삽입 경로와 빌드 뒤 화면 확인이 필요하다.
"""
import _utf8  # noqa: F401  (출력 UTF-8)
import argparse
import csv
import sys
from pathlib import Path

import numpy as np
from PIL import Image

IMG_EXT = ('.png', '.bmp', '.tga', '.gif')


def _rects(path, need_kind=False):
    out = {}
    if not path:
        return out
    with open(path, encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            key = (r.get('file') or '').replace('\\', '/').strip()
            if not key:
                continue
            box = tuple(int(float(r[k])) for k in ('x0', 'y0', 'x1', 'y1'))
            kind = (r.get('kind') or 'edit').strip().lower() if need_kind else 'visible'
            if kind not in ('edit', 'keep', 'visible'):
                raise SystemExit(f'imgbox: {path} 의 kind 는 edit 또는 keep: {kind!r}')
            out.setdefault(key, []).append((box, kind))
    return out


def _lookup(table, rel):
    return table.get(rel) or table.get(Path(rel).name) or []


def _mask(shape, boxes):
    m = np.zeros(shape, bool)
    for (x0, y0, x1, y1), _ in boxes:
        m[max(0, y0):max(0, y1), max(0, x0):max(0, x1)] = True
    return m


def check_pair(orig, result, boxes, visible=None, transparent='auto'):
    """한 쌍 → dict. boxes = [((x0,y0,x1,y1), 'edit'|'keep')], visible = [((x0,y0,x1,y1), _)] 또는 None(전체)."""
    io, ir = Image.open(orig), Image.open(result)
    has_alpha = io.mode in ('RGBA', 'LA', 'PA') or (io.mode == 'P' and 'transparency' in io.info)
    a, b = np.asarray(io.convert('RGBA')), np.asarray(ir.convert('RGBA'))
    r = {'size': f'{io.width}x{io.height}', 'verdict': 'PASS', 'note': ''}
    if a.shape != b.shape:
        r.update(verdict='FAIL', note=f'크기 다름: 결과 {ir.width}x{ir.height}')
        return r
    hw = a.shape[:2]
    diff = (a != b).any(axis=2)
    edit = _mask(hw, [x for x in boxes if x[1] == 'edit'])
    keep = _mask(hw, [x for x in boxes if x[1] == 'keep'])
    vis = _mask(hw, visible) if visible else np.ones(hw, bool)
    if transparent == 'none' or (transparent == 'auto' and not has_alpha):
        trans = np.zeros(hw, bool)
    elif transparent in ('auto', 'alpha'):
        trans = a[:, :, 3] == 0
    elif transparent.startswith('rgb:'):
        rgb = [int(v) for v in transparent[4:].split(',')]
        trans = (a[:, :, :3] == rgb).all(axis=2)
    else:
        raise SystemExit(f'imgbox: --transparent 는 auto·alpha·rgb:R,G,B·none: {transparent!r}')
    outside = diff & ~edit & vis
    r.update(changed=int(diff.sum()), inside=int((diff & edit).sum()), outside=int(outside.sum()),
             offscreen=int((diff & ~vis).sum()), keep=int((diff & keep).sum()),
             transparent_outside=int((diff & trans & ~edit).sum()), transparent_inside=int((diff & trans & edit).sum()))
    if outside.any():
        ys, xs = np.nonzero(outside)
        r['outside_bbox'] = f'{xs.min()},{ys.min()}-{xs.max() + 1},{ys.max() + 1}'
    if r['outside'] or r['offscreen'] or r['keep']:
        r['verdict'] = 'FAIL'
    elif r['transparent_inside']:
        r['note'] = '알파 확인 — 상자 안 투명 칸이 바뀜(알파 재생성 삽입 경로·빌드 뒤 화면 확인)'
    return r


COLS = ['file', 'verdict', 'size', 'changed', 'inside', 'outside', 'offscreen', 'keep',
        'transparent_outside', 'transparent_inside', 'outside_bbox', 'note']


def run(orig, result, boxes_csv, visible_csv=None, visible_rect=None, transparent='auto'):
    orig, result = Path(orig), Path(result)
    boxes, vis = _rects(boxes_csv, need_kind=True), _rects(visible_csv)
    rect = [(tuple(int(v) for v in visible_rect.split(',')), 'visible')] if visible_rect else None
    if result.is_file():
        pairs = [(orig if orig.is_file() else orig / result.name, result, result.name)]
    else:
        pairs = [(orig / p.relative_to(result), p, p.relative_to(result).as_posix())
                 for p in sorted(result.rglob('*')) if p.suffix.lower() in IMG_EXT]
    rows = []
    for o, res, rel in pairs:
        if not o.is_file():
            rows.append({'file': rel, 'verdict': 'FAIL', 'note': f'원본 없음: {o}'})
            continue
        r = check_pair(o, res, _lookup(boxes, rel), _lookup(vis, rel) or rect, transparent)
        r['file'] = rel
        if not _lookup(boxes, rel) and r.get('changed'):
            r['note'] = (r['note'] + ' ' if r['note'] else '') + '상자 없음'
        rows.append(r)
    return rows


def write(path, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=COLS, lineterminator='\n', extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)


def main(argv=None, default_out=None):
    ap = argparse.ArgumentParser(prog='imgbox', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--orig', required=True, help='원본 PNG 또는 폴더')
    ap.add_argument('--result', required=True, help='결과 PNG 또는 폴더(이 안의 그림을 모두 본다)')
    ap.add_argument('--boxes', required=True, help='상자 CSV (file,x0,y0,x1,y1,kind)')
    ap.add_argument('--visible', help='화면 범위 CSV (file,x0,y0,x1,y1)')
    ap.add_argument('--visible-rect', help='모든 그림에 같은 화면 범위 x0,y0,x1,y1')
    ap.add_argument('--transparent', default='auto')
    ap.add_argument('--out', default=default_out)
    a = ap.parse_args(argv)
    rows = run(a.orig, a.result, a.boxes, a.visible, a.visible_rect, a.transparent)
    if a.out:
        write(a.out, rows)
    bad = [r for r in rows if r['verdict'] != 'PASS']
    for r in bad[:30]:
        print(f"  FAIL {r['file']}: 상자 밖 {r.get('outside', '-')} · 화면 밖 {r.get('offscreen', '-')} · 유지 {r.get('keep', '-')}"
              f" · 상자 밖 투명 칸 {r.get('transparent_outside', '-')} {r.get('outside_bbox', '')} {r.get('note', '')}".rstrip())
    alpha = sum(1 for r in rows if r['verdict'] == 'PASS' and r.get('transparent_inside'))
    print(f"그림 {len(rows)}장: PASS {len(rows) - len(bad)} · FAIL {len(bad)}" + (f' · 알파 확인 {alpha}' if alpha else '')
          + (f' -> {a.out}' if a.out else ''))
    print('imgbox', 'FAIL' if bad else 'PASS')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
