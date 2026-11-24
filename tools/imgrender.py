# -*- coding: utf-8 -*-
"""imgrender — 그림에 한글을 그리는 함수 모음 (투명 글씨·배경 글씨의 「직접 렌더」).

계열(같은 모양의 그림 묶음)마다 작업 폴더의 render/<계열>.py 를 짜서 이 모듈을 불러 쓴다. 예: examples/render_series.py

    import sys; sys.path.insert(0, r'<키트>/tools')
    from imgrender import *
    init(work=r'<작업 폴더>')                    # src/ · ko/ · grids/ 가 있는 폴더 (기본: 지금 폴더)
    run('', '그림이름', lambda b: dict(spec=('NSB', 16), fallback=[('NSB', 15)], align='center', color='auto'))

하는 일 (run):
  - 지우기: 상자(분류 clear, 원래 번호 3) 안 알파를 0. 지우는 자리에 닿은 잉크 덩어리(외곽선·그림자·삐침)는 상자 밖으로
    넘쳐도 spill_px 안에서 함께 지운다. keep 상자·protect_extra·다른 스프라이트는 건드리지 않는다.
  - 그리기: 줄마다 원본 잉크의 세로 중심·가로 기준점(left/center/right)을 재서 맞춘다. 칸(clip)을 넘으면 ±2px 옮겨 보고,
    그래도 넘치면 fallback 크기·spacings 자간 순으로. 같은 _group 은 모두 들어가는 가장 큰 조합 하나로.
  - 글꼴: spec=(키, 크기[, 'snap'[, 장평]]). 화소 글꼴 키(G7·G9·G11·G11B)는 제 크기, 벡터 글꼴은 크기 px.
    원문 충실: spec=(키, 'orig') 면 원문 글자 높이에 맞춘 벡터 크기에서 시작해 자간 → 장평 0.9·0.8 → 작은 크기.
    원문이 도트 글씨(ink_kind)면 style 의 pixel=[화소 spec] 을 먼저, 매끈한 글씨인데 벡터가 뭉개지면(blurry) 그때만 화소.
    계열: run_series(pack, 이름들, style) — 원문 크기가 같은 묶음은 모든 그림에서 같은 글꼴·크기(장평까지).
    'snap' = 작은 벡터를 8배로 그려 글자마다 1/8 화소 위치를 골라 세로획을 격자에 맞춘다(ㅐ·ㅔ 두 획이 붙지 않게).
  - 효과: color('auto' = 원본 잉크 밝기 90 백분위) · outline · glow · shadow · char_colors · scale_chars.
  - 결과: ko/<pack>/<이름>.png (원본과 같은 크기), 상자마다 쓴 글꼴·자간 또는 「칸에 안 들어감」을 report 로.

글꼴은 키트 fonts/ (또는 IMGKIT_FONTS) 아래 어디에 있든 파일 이름으로 찾는다. 없는 키는 register() 로 더한다.
게임이 그림을 스프라이트 사각형으로 잘라 쓰면 set_sprites(함수) 로 알려 준다(상자에 든 스프라이트는 통째로 지우고,
다른 스프라이트는 지킨다). 모르면 두지 않는다.

"""
import csv
import json
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter  # noqa: F401  (계열 스크립트가 같이 쓴다)
from scipy import ndimage as nd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _utf8  # noqa: E402,F401
from imggrid import norm_class  # noqa: E402

KIT = Path(__file__).resolve().parent.parent
WORK = Path(os.environ.get('IMGKIT_WORK') or '.').resolve()
SRC = str(WORK / 'src')
OUT = str(WORK / 'ko')
GRIDS = str(WORK / 'grids')
FONTDIR = Path(os.environ.get('IMGKIT_FONTS') or (KIT / 'fonts'))


def init(work=None, src=None, out=None, grids=None, fonts=None):
    """작업 폴더를 정한다. src·out·grids 를 따로 주면 그것을(기본 work/src · work/ko · work/grids)."""
    global WORK, SRC, OUT, GRIDS, FONTDIR
    if work:
        WORK = Path(work).resolve()
    SRC = str(Path(src).resolve()) if src else str(WORK / 'src')
    OUT = str(Path(out).resolve()) if out else str(WORK / 'ko')
    GRIDS = str(Path(grids).resolve()) if grids else str(WORK / 'grids')
    if fonts:
        FONTDIR = Path(fonts)
    _FPATH.clear()


# ---------------------------------------------------------------- 글꼴 목록
# 화소 글꼴: 키 → (파일 이름, 제 크기)
PIXEL = {
    'G7': ('Galmuri7.ttf', 8),       # Galmuri7.ttf 는 8 이 한글 7px (Bitmap 판은 10)
    'G9': ('Galmuri9.ttf', 10),
    'G11': ('Galmuri11.ttf', 12),
    'G11B': ('Galmuri11-Bold.ttf', 12),
    'NEODGM': ('neodgm.ttf', 16),
}
# 벡터 글꼴: 키 → 파일 이름, 또는 (가변 글꼴 파일 이름, 굵기 이름)
VECTOR = {
    'PRET': 'Pretendard-Regular.otf',
    'PRETB': 'Pretendard-Bold.otf',
    'NSANS': ('NotoSansKR-VariableFont_wght.ttf', b'Regular'),
    'NSANSB': ('NotoSansKR-VariableFont_wght.ttf', b'Bold'),
    'NSR': ('NotoSerifKR-VariableFont_wght.ttf', b'Regular'),
    'NSB': ('NotoSerifKR-VariableFont_wght.ttf', b'Bold'),
    'NSEB': ('NotoSerifKR-VariableFont_wght.ttf', b'ExtraBold'),
    'MJ': 'NanumMyeongjo.ttf',
    'MJB': 'NanumMyeongjoBold.ttf',
    'MJEB': 'NanumMyeongjoExtraBold.ttf',
    'BHS': 'BlackHanSans-Regular.ttf',
    'PEN': 'NanumPenScript-Regular.ttf',
    'BRUSH': 'NanumBrushScript-Regular.ttf',
    'HAM': ('Hahmlet[wght].ttf', b'Regular'),
    'HAMM': ('Hahmlet[wght].ttf', b'Medium'),
    'HAMB': ('Hahmlet[wght].ttf', b'Bold'),
    'HAMEB': ('Hahmlet[wght].ttf', b'ExtraBold'),
    'GOWUN': 'GowunBatang-Regular.ttf',
    'GOWUNB': 'GowunBatang-Bold.ttf',
}
# 글꼴에 없는 글자: 글꼴 키 → {글자: (대신 쓸 글꼴 키 또는 None(같은 글꼴), 대신 그릴 글자)}
_HAM_SUB_R = {'：': (None, ':'), '『': ('GOWUN', '『'), '』': ('GOWUN', '』')}
_HAM_SUB_B = {'：': (None, ':'), '『': ('GOWUNB', '『'), '』': ('GOWUNB', '』')}
SUBST = {'HAM': _HAM_SUB_R, 'HAMM': _HAM_SUB_R, 'HAMB': _HAM_SUB_B, 'HAMEB': _HAM_SUB_B}

_FPATH = {}


def register(key, file, size=None, weight=None, pixel=False):
    """글꼴 키를 더하거나 바꾼다. file = fonts/ 아래 파일 이름(또는 경로). pixel=True 면 size 가 제 크기.
    weight = 가변 글꼴의 굵기 이름(예 'Bold')."""
    if pixel:
        PIXEL[key] = (file, size)
    else:
        VECTOR[key] = (file, weight.encode() if isinstance(weight, str) else weight) if weight else file


def font_path(file):
    """fonts/ 아래에서 파일 이름으로 찾는다 (하위 폴더 어디든). 경로를 주면 그대로."""
    if file in _FPATH:
        return _FPATH[file]
    p = Path(file)
    if p.is_file():
        _FPATH[file] = str(p)
        return str(p)
    if (FONTDIR / file).is_file():
        _FPATH[file] = str(FONTDIR / file)
        return _FPATH[file]
    hits = sorted(FONTDIR.rglob(p.name)) if FONTDIR.is_dir() else []
    if not hits:
        raise SystemExit(f'imgrender: 글꼴 {p.name} 이 {FONTDIR} 아래에 없다 — FONTS.md 를 보고 받아 둔다 (또는 register 로 다른 파일)')
    _FPATH[file] = str(hits[0])
    return _FPATH[file]


# ---------------------------------------------------------------- 스프라이트 (선택)
_SPRITES = None


def set_sprites(func):
    """func(파일 이름) → [(키, (x0, y0, x1, y1)), …] — 게임이 그림을 잘라 쓰는 사각형. 모르면 쓰지 않는다."""
    global _SPRITES
    _SPRITES = func


def meta(fname):
    return list(_SPRITES(fname) or []) if _SPRITES else []


def subst(key, ch):
    """(글꼴 키, 그릴 글자) — 함렛에 없는 글자는 SUBST 대로."""
    k2, c2 = SUBST.get(key, {}).get(ch, (None, ch))
    return (k2 or key), c2
REF = '한글가나다'  # 세로 위치 기준(낱자마다 위치가 뛰지 않게)

def boxes(name):
    rows = list(csv.DictReader(open(f'{GRIDS}/BOXES_{name}.csv', encoding='utf-8-sig')))
    for r in rows:
        r['rect'] = tuple(int(r[k]) for k in ('x0', 'y0', 'x1', 'y1'))
    return rows


def inside(a, b, pad=4):
    return a[0] >= b[0] - pad and a[1] >= b[1] - pad and a[2] <= b[2] + pad and a[3] <= b[3] + pad


def overlap(a, b):
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))


# ---------------------------------------------------------------- 글꼴
def font(spec):
    """spec: ('G11',) 화소 / ('MJB', 15) 벡터"""
    key = spec[0]
    if key in PIXEL:
        f, s = PIXEL[key]
        return ImageFont.truetype(font_path(f), s), True
    v = VECTOR[key]
    if isinstance(v, tuple):
        ft = ImageFont.truetype(font_path(v[0]), spec[1])
        ft.set_variation_by_name(v[1])
        return ft, False
    return ImageFont.truetype(font_path(v), spec[1]), False


NL = chr(92) + 'n'   # 격자 파일 ko 의 줄바꿈 표기 (백슬래시와 n 두 글자)
SNAP_S = 8  # 'snap' 벡터: 8배로 그려 8x8 평균으로 줄인다(1/8 화소 위치)


_FCACHE = {}


def _bigfont(key, size):
    k = (key, size)
    if k not in _FCACHE:
        v = VECTOR[key]
        f = ImageFont.truetype(font_path(v[0] if isinstance(v, tuple) else v), size)
        if isinstance(v, tuple):
            f.set_variation_by_name(v[1])
        _FCACHE[k] = f
    return _FCACHE[k]


_GCACHE = {}


def _snap_mask(text, spec, spacing):
    """작은 벡터 글꼴(14px 미만)용. Pillow 는 글자 위치를 정수 화소로 반올림하고 힌팅이 ㅐ·ㅔ 두 세로획을
    한 덩어리로 붙인다(title__TITLE_0 b12 「새」 judge 불합격). 그래서 8배 크기로 그리고, 글자마다 가로 위치를
    1/8 화소 단위로 ±1/2 화소 안에서 옮겨 보아 줄인 결과가 가장 또렷한(Σa²/Σa 최대) 위치를 고른다. 세로 위치(1/8 화소)는
    줄 전체에 하나. 같은 입력이면 같은 결과(결정적). 함렛에 없는 글자는 SUBST(기준선 맞춤)."""
    S = SNAP_S
    key = spec[0]
    xsc = spec[3] if len(spec) > 3 and spec[3] else 1   # 장평(가로 비율). 1 이면 예전과 똑같이
    big = _bigfont(key, spec[1] * S)
    asc = big.getmetrics()[0]
    spacing, space_adj = spacing if isinstance(spacing, tuple) else (spacing, 0)
    size = spec[1]
    W = int(big.getlength(text) / S * 2 + 40 + len(text) * abs(spacing))
    H = int(size * 3 + 20)
    oy = int(size)

    def down(bigarr):
        h, w = bigarr.shape
        return bigarr[:h - h % S, :w - w % S].reshape(h // S, S, w // S, S).mean((1, 3)) / 255

    def glyph(ch, bx, by):
        # 글자 둘레만 작은 캔버스에 그려 전체 줄 크기로 옮긴다(빠르게, 같은 1/8 위치는 다시 쓰기)
        k2, c2 = subst(key, ch)
        f2 = _bigfont(k2, spec[1] * S)
        by2 = by + asc - f2.getmetrics()[0]
        ix = bx // S - 3
        ck = (k2, spec[1], c2, bx - ix * S, by2, H, xsc)
        if ck not in _GCACHE:
            cw = int(f2.getlength(c2) / S) + 8
            if xsc == 1:
                im = Image.new('L', (cw * S, H * S), 0)
                ImageDraw.Draw(im).text((bx - ix * S, by2), c2, font=f2, fill=255)
            else:
                # 장평: 펼친 캔버스에 그려 가로만 xsc 배로 줄인다(8배 해상도에서) — 글자 왼끝이 bx 에 오게
                wide = Image.new('L', (int(np.ceil(cw * S / xsc)), H * S), 0)
                ImageDraw.Draw(wide).text(((bx - ix * S) / xsc, by2), c2, font=f2, fill=255)
                im = wide.resize((cw * S, H * S), Image.BOX)
            _GCACHE[ck] = down(np.array(im).astype(float))
        small = _GCACHE[ck]
        out = np.zeros((H, W))
        n = min(small.shape[1], W - ix)
        out[:, ix:ix + n] = small[:, :n]
        return out

    def adv(ch):
        k2, c2 = subst(key, ch)
        return _bigfont(k2, spec[1] * S).getlength(c2) / S * xsc

    def sharp(a):
        t = a.sum()
        return (a * a).sum() / t if t > 0 else 0

    # 글자 기본 위치(1/8 화소 단위)
    pos = []
    x = 10.0
    for ch in text:
        pos.append(int(round(x * S)))
        x += adv(ch) + spacing + (space_adj if ch == ' ' else 0)
    best = None
    for ph_y in range(S):
        by = oy * S + ph_y
        glyphs, total = [], 0.0
        for ch, bx in zip(text, pos):
            if not ch.strip():
                glyphs.append(None)
                continue
            cands = []
            for d in sorted(range(-S // 2, S // 2), key=lambda t: (abs(t), t)):
                g = glyph(ch, bx + d, by)
                cands.append((round(sharp(g), 6), -abs(d), g))
            sc, _, g = max(cands, key=lambda c: (c[0], c[1]))
            glyphs.append(g)
            total += sc
        if best is None or total > best[0] + 1e-9:
            best = (total, ph_y, glyphs)
    _, ph_y, glyphs = best
    a = np.zeros((H, W))
    char_idx = np.zeros((H, W), np.int16) - 1
    for i, g in enumerate(glyphs):
        if g is None:
            continue
        a = np.maximum(a, g)
        char_idx[g > 0] = i
    # 세로 기준: REF 를 같은 방법으로
    ref = glyph(REF, 10 * S, oy * S + ph_y)
    rr = np.nonzero(ref.max(1) > 0.5)[0]
    return a, (rr[0], rr[-1]), char_idx


def text_mask(text, spec, spacing=0, scale_chars=None):
    """글자 알파 마스크(0..1)와 기준 상자. scale_chars={i: (spec2, color)} 는 글자별 다른 글꼴(219003 「목」).
    spec 세 번째가 'snap' 이면 _snap_mask(작은 벡터 글꼴의 세로획을 화소 격자에 맞춤)."""
    if len(spec) > 2 and spec[2] == 'snap' and not scale_chars:
        return _snap_mask(text, spec, spacing)
    ft, pix = font(spec)
    # spacing: 글자 사이(px) 또는 (글자 사이, 띄어쓰기 칸에만 더할 px)
    #   또는 ('tight', k): 글자마다 앞 글자 잉크와 1px 이상 떨어진 채로 최대 k px 당긴다(획이 닿지 않게 좁히기).
    #   띄어쓰기 바로 뒤 글자는 당기지 않는다(낱말 사이 유지).
    tight, gap = 0, 1
    if isinstance(spacing, tuple) and spacing[0] == 'tight':
        tight, gap, spacing = spacing[1], (spacing[2] if len(spacing) > 2 else 1), 0
    spacing, space_adj = spacing if isinstance(spacing, tuple) else (spacing, 0)
    W = int(ft.getlength(text) * 2 + 40 + len(text) * abs(spacing))
    H = int(ft.size * 3 + 20)
    img = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(img)
    if pix:
        d.fontmode = '1'
    oy = ft.size
    x = 10.0
    char_idx = np.zeros((H, W), np.int16) - 1
    for i, ch in enumerate(text):
        f2, p2 = ft, pix
        k2, ch = subst(spec[0], ch)
        if k2 != spec[0]:
            f2, p2 = font((k2,) + tuple(spec[1:2]))
        if scale_chars and i in scale_chars:
            f2, p2 = font(scale_chars[i][0])
        tmp = Image.new('L', (W, H), 0)
        d2 = ImageDraw.Draw(tmp)
        if p2:
            d2.fontmode = '1'
        # 기준선 맞춤
        asc = ft.getmetrics()[0]
        asc2 = f2.getmetrics()[0]
        d2.text((round(x), oy + asc - asc2), ch, font=f2, fill=255)
        t = np.array(tmp)
        if tight and i > 0 and text[i - 1] != ' ' and ch.strip():
            prev = nd.binary_dilation(np.array(img) > 40, structure=np.ones((3, 3)), iterations=gap)
            best = 0
            for sft in range(1, tight + 1):
                t2 = np.zeros_like(t)
                t2[:, :-sft] = t[:, sft:]
                if ((t2 > 40) & prev).any():
                    break
                best = sft
            if best:
                t2 = np.zeros_like(t)
                t2[:, :-best] = t[:, best:]
                t = t2
                x -= best
        img = Image.fromarray(np.maximum(np.array(img), t))
        char_idx[t > 0] = i
        x += f2.getlength(ch) + spacing + (space_adj if ch == ' ' else 0)
    a = np.array(img).astype(float) / 255
    # 세로 기준: REF 의 잉크 위아래
    ref = Image.new('L', (W, H), 0)
    dr = ImageDraw.Draw(ref)
    if pix:
        dr.fontmode = '1'
    dr.text((10, oy), REF, font=ft, fill=255)
    ra = np.array(ref)
    rr = np.nonzero(ra.max(1) > 0)[0]
    return a, (rr[0], rr[-1]), char_idx


# ---------------------------------------------------------------- 원본 재기
def core_mask(arr, rect, mode='bright', frac=None):
    """글자 잉크 마스크. frac = 알파 문턱(그 상자 최대 알파에 대한 비율) — 주지 않으면 갈래(mode)의 기본값."""
    x0, y0, x1, y1 = rect
    s = arr[y0:y1, x0:x1].astype(float)
    a = s[..., 3]
    lum = s[..., :3].mean(2)
    if a.max() == 0:
        return np.zeros(a.shape, bool)
    if mode == 'alpha':
        return a >= (frac or 0.45) * a.max()
    if mode == 'loose':
        return a >= (frac or 0.25) * a.max()
    return (a >= (frac or 0.5) * a.max()) & (lum >= 0.6 * lum[a > 0].max())


def lines_of(arr, rect, n, mode='bright', min_gap=1):
    """상자 안 잉크 줄을 위에서부터 n 개로 나눠 각 줄 (top, bottom, left, right) — 원본 좌표.
    위·아래: 진한 잉크(core_mask)의 행. 줄 위아래 끝에서 잉크가 아주 적은 행(탁점 ゛゜·점 — 그 줄에서 가장
    많은 행의 8% 미만)은 몸통이 아니라 뺀다. 왼쪽·오른쪽: 흐린 가장자리까지(알파가 최대의 15% 이상) — 첫 획이
    흐린 글씨도 실제 시작점에 맞도록."""
    m = core_mask(arr, rect, mode)
    lm = core_mask(arr, rect, mode, 0.15)
    rows = m.any(1)
    runs = []
    st = None
    for i, v in enumerate(list(rows) + [False]):
        if v and st is None:
            st = i
        if not v and st is not None:
            runs.append([st, i - 1])
            st = None
    # 너무 작은 조각(점·탁점)은 가까운 줄에 붙인다
    while len(runs) > n:
        gaps = [runs[i + 1][0] - runs[i][1] for i in range(len(runs) - 1)]
        sizes = [r[1] - r[0] for r in runs]
        i = int(np.argmin(gaps))
        runs[i] = [runs[i][0], runs[i + 1][1]]
        del runs[i + 1]
    if len(runs) != n:
        raise ValueError(f'줄 수가 다르다 {rect} {len(runs)} != {n}')
    out = []
    for t, b in runs:
        cnt = m[t:b + 1].sum(1)
        body = np.nonzero(cnt >= 0.08 * cnt.max())[0]
        t, b = t + body[0], t + body[-1]
        cols = np.nonzero(lm[t:b + 1].any(0))[0]
        out.append((rect[1] + t, rect[1] + b, rect[0] + cols[0], rect[0] + cols[-1]))
    return out


# ---------------------------------------------------------------- 지우기
def erase(arr, name, fname, edit_rects, protect_extra=(), spill_px=6):
    """edit_rects: 지울 사각형 목록. 메타 스프라이트 중 지울 사각형 안에 든 것은 통째로 지우고,
    나머지 스프라이트·protect_extra 는 지키며, 지울 자리에 닿은 잉크 덩어리를 함께 지운다."""
    H, W = arr.shape[:2]
    er = np.zeros((H, W), bool)
    sprites = meta(fname)
    textsp = []
    for r in edit_rects:
        er[r[1]:r[3], r[0]:r[2]] = True
        for k, sr in sprites:
            if inside(sr, r):
                er[sr[1]:sr[3], sr[0]:sr[2]] = True
                textsp.append(sr)
    prot = np.zeros((H, W), bool)
    for k, sr in sprites:
        if sr in textsp:
            continue
        if any(inside(sr, r) for r in edit_rects):
            continue
        area = (sr[2] - sr[0]) * (sr[3] - sr[1])
        if any(overlap(sr, r) >= 0.1 * area for r in edit_rects):
            continue   # 글자 스프라이트의 일부만 바꾸는 경우(스프라이트 안 기호 하나만 남기는 경우 등)
        prot[sr[1]:sr[3], sr[0]:sr[2]] = True
    for r in protect_extra:
        prot[r[1]:r[3], r[0]:r[2]] = True
    # 지키는 스프라이트의 가장자리 번짐(아틀라스 여백에 가장자리 화소를 1px 복사해 둔 것)도 지킨다
    for k, sr in sprites:
        if sr in textsp or any(inside(sr, r) for r in edit_rects):
            continue
        area = (sr[2] - sr[0]) * (sr[3] - sr[1])
        if any(overlap(sr, r) >= 0.1 * area for r in edit_rects):
            continue
        x0, y0, x1, y1 = sr
        xa, xb = max(0, x0 - 1), min(W, x1 + 1)
        ya, yb = max(0, y0 - 1), min(H, y1 + 1)
        def same(ay, ax, by, bx):
            return np.all(arr[ay, ax] == arr[by, bx], axis=-1)
        if y0 - 1 >= 0:
            prot[y0 - 1, x0:x1] |= same(y0 - 1, slice(x0, x1), y0, slice(x0, x1)) & (arr[y0 - 1, x0:x1, 3] > 0)
        if y1 < H:
            prot[y1, x0:x1] |= same(y1, slice(x0, x1), y1 - 1, slice(x0, x1)) & (arr[y1, x0:x1, 3] > 0)
        if x0 - 1 >= 0:
            prot[y0:y1, x0 - 1] |= same(slice(y0, y1), x0 - 1, slice(y0, y1), x0) & (arr[y0:y1, x0 - 1, 3] > 0)
        if x1 < W:
            prot[y0:y1, x1] |= same(slice(y0, y1), x1, slice(y0, y1), x1 - 1) & (arr[y0:y1, x1, 3] > 0)
        for cy, cx, iy, ix in [(y0 - 1, x0 - 1, y0, x0), (y0 - 1, x1, y0, x1 - 1), (y1, x0 - 1, y1 - 1, x0), (y1, x1, y1 - 1, x1 - 1)]:
            if 0 <= cy < H and 0 <= cx < W and arr[cy, cx, 3] > 0 and np.all(arr[cy, cx] == arr[iy, ix]):
                prot[cy, cx] = True
    # 지울 자리에 닿은 잉크 덩어리(넘친 외곽선·그림자)
    ink = arr[..., 3] > 0
    lab, nlab = nd.label(ink & ~prot, structure=np.ones((3, 3)))
    hit = np.unique(lab[er & ~prot & ink])
    hit = hit[hit > 0]
    spill = np.isin(lab, hit)
    # 덩어리가 너무 멀리(상자에서 6px 넘게) 뻗으면 다른 그림이다 — 6px 안만
    near = nd.binary_dilation(er, iterations=spill_px) if spill_px else er
    mask = ((er | (spill & near)) & ~prot)
    arr[mask, 3] = 0
    arr[mask, :3] = 0
    return mask


# ---------------------------------------------------------------- 그리기
def compose(arr, glyph, gx, gy, color=(255, 255, 255), alpha=1.0, outline=None, glow=None, shadow=None,
            clip=None, char_idx=None, char_colors=None, ink_alpha=None, grad=None):
    """glyph(0..1) 을 arr 의 (gx,gy) 에 얹는다. 효과는 글자 아래에 먼저 깐다.
    ink_alpha=0..255 — 겹쳐 얹지 않고 글자 화소를 (색, 이 알파)로 써 넣는다(덮임 정도만큼 바탕과 섞음).
      반투명 띠·판 위 글씨처럼 원문 글자 화소의 알파가 일정한 값(예 126)일 때.
    grad=(y위, (r,g,b), y아래, (r,g,b)) — 글자색 세로 그러데이션(그림 좌표 y 기준, 그 밖은 끝 색). measure_grad 로 잰다.
    outline=(반지름, (r,g,b), 알파) — 원판 팽창. glow=(반지름, 흐림, (r,g,b), 알파). shadow=((dx,dy),(r,g,b),알파).
    clip=(x0,y0,x1,y1): 이 밖으로 나가는 잉크가 있으면 ValueError(칸 넘침)."""
    h, w = glyph.shape
    pad = 6
    G = np.zeros((h + 2 * pad, w + 2 * pad))
    G[pad:pad + h, pad:pad + w] = glyph
    layers = []  # (alpha 0..1, rgb)
    if glow:
        r, blur, col, al = glow
        m = nd.binary_dilation(G > 0.25, iterations=r).astype(float)
        if blur:
            m = nd.gaussian_filter(m, blur)
            m = np.clip(m * 1.6, 0, 1)
        layers.append((m * al, col))
    if shadow:
        (dx, dy), col, al = shadow
        m = np.roll(np.roll(G, dy, 0), dx, 1)
        layers.append((m * al, col))
    if outline:
        r, col, al = outline
        if r > 0:
            st = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]]) if r == 1 else np.ones((3, 3))
            m = nd.grey_dilation(G, footprint=st) if r == 1 else nd.grey_dilation(G, size=(2 * r + 1, 2 * r + 1))
            layers.append((m * al, col))
    # 글자
    cc = np.zeros(G.shape + (3,))
    cc[:] = color
    if grad:
        yt, ct, yb, cb = grad
        Y = np.arange(G.shape[0]) + gy - pad
        t = np.clip((Y - yt) / max(1e-6, yb - yt), 0, 1)[:, None]
        cc[:] = (np.array(ct, float) + (np.array(cb, float) - np.array(ct, float)) * t)[:, None, :]
    if char_idx is not None and char_colors:
        CI = np.full(G.shape, -1, np.int16)
        CI[pad:pad + h, pad:pad + w] = char_idx
        for i, c in char_colors.items():
            cc[CI == i] = c
    layers.append((G * alpha, cc))
    # 합성(투명 바탕 위 over 연산)
    outA = np.zeros(G.shape)
    outC = np.zeros(G.shape + (3,))
    for a, c in layers:
        c = np.broadcast_to(np.array(c, float), G.shape + (3,)) if not isinstance(c, np.ndarray) else c
        na = a + outA * (1 - a)
        with np.errstate(invalid='ignore', divide='ignore'):
            outC = np.where(na[..., None] > 0, (c * a[..., None] + outC * outA[..., None] * (1 - a[..., None])) / na[..., None], 0)
        outA = na
    X0, Y0 = gx - pad, gy - pad
    ys, xs = np.nonzero(outA > 0.02)
    if clip is not None and len(xs):
        if X0 + xs.min() < clip[0] or Y0 + ys.min() < clip[1] or X0 + xs.max() >= clip[2] or Y0 + ys.max() >= clip[3]:
            raise ValueError(f'칸 넘침: 잉크 x{X0 + xs.min()}~{X0 + xs.max()} y{Y0 + ys.min()}~{Y0 + ys.max()} / 칸 {clip}')
    H, W = arr.shape[:2]
    for y, x in zip(ys, xs):
        Y, Xx = Y0 + y, X0 + x
        if not (0 <= Y < H and 0 <= Xx < W):
            continue
        a = outA[y, x]
        if ink_alpha is not None:
            tgt = np.append(outC[y, x], ink_alpha)
            arr[Y, Xx] = np.clip(np.round(arr[Y, Xx] + (tgt - arr[Y, Xx]) * a), 0, 255)
            continue
        da = arr[Y, Xx, 3] / 255.0
        na = a + da * (1 - a)
        if na <= 0:
            continue
        rgb = (outC[y, x] * a + arr[Y, Xx, :3] * da * (1 - a)) / na
        arr[Y, Xx, :3] = np.clip(np.round(rgb), 0, 255)
        arr[Y, Xx, 3] = int(round(na * 255))


def _condensed(text, spec, spacing, scale_chars):
    S = 4
    xs = spec[3]
    if isinstance(spacing, tuple) and spacing[0] == 'tight':
        sp4 = ('tight', spacing[1] * S, S)
    elif isinstance(spacing, tuple):
        sp4 = (spacing[0] * S, spacing[1] * S)
    else:
        sp4 = spacing * S
    sc4 = {i: ((v[0][0], v[0][1] * S),) + tuple(v[1:]) for i, v in scale_chars.items()} if scale_chars else None
    a, (rt, rb), ci = text_mask(text, (spec[0], spec[1] * S), sp4, sc4)
    h, w = a.shape
    H2, W2 = -(-h // S), int(np.ceil(w * xs / S))
    im = Image.fromarray(np.clip(a * 255, 0, 255).astype(np.uint8)).resize((W2, H2), Image.BOX)
    ci2 = np.array(Image.fromarray((ci + 1).astype(np.int32)).resize((W2, H2), Image.NEAREST)).astype(np.int16) - 1
    return np.array(im).astype(float) / 255, (rt // S, rb // S), ci2


def place(arr, text, spec, line, align, clip, spacing=0, dx=0, dy=0, **fx):
    """line=(top,bottom,left,right) 원본 글자 몸통. 세로 중심·가로 기준점을 맞춘다.
    spec 네 번째 값이 있으면 가로 비율(장평, 예 0.9): 4배로 그려 가로만 그만큼 줄여 내린다.
    세 번째가 'snap' 이면 _snap_mask 가 장평까지 함께 처리한다(8배, 글자마다 1/8 화소 위치 고르기)."""
    if len(spec) > 3 and spec[3] != 1 and spec[2] != 'snap':
        a, (rt, rb), ci = _condensed(text, spec, spacing, fx.pop('scale_chars', None))
    else:
        a, (rt, rb), ci = text_mask(text, spec if len(spec) > 3 and spec[2] == 'snap' else spec[:3], spacing, fx.pop('scale_chars', None))
    ys, xs = np.nonzero(a > 0)
    gl = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    ci = ci[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    # 세로: REF 잉크 중심 ↔ 원본 줄 중심
    ref_c = (rt + rb) / 2 - ys.min()
    tgt_c = (line[0] + line[1]) / 2
    gy = int(round(tgt_c - ref_c)) + dy
    w = gl.shape[1]
    if align == 'left':
        gx = line[2]
    elif align == 'right':
        gx = line[3] - w + 1
    else:
        gx = int(round((line[2] + line[3]) / 2 - (w - 1) / 2))
    gx += dx
    # 칸에 1~2px 걸리면 기준점 ±2px 안에서 옮겨 본다(원본 잉크 기준 허용 범위)
    err = None
    for sx, sy in sorted([(a, b) for a in range(-2, 3) for b in range(-2, 3)], key=lambda t: (abs(t[0]) + abs(t[1]), abs(t[0]))):
        if align == 'left' and sx < 0 and gx + sx < line[2] - 2:
            continue
        try:
            compose(arr, gl, gx + sx, gy + sy, clip=clip, char_idx=ci, **fx)
            return dict(x=gx + sx, y=gy + sy, gl=gl, ci=ci)
        except ValueError as e:
            err = err or e
    raise err


def fit_width(text, specs, spacings=(0, -1)):
    """(spec, spacing, 폭) 목록 — 큰 것부터."""
    out = []
    for s in specs:
        for sp in spacings:
            a, _, _ = text_mask(text, s, sp)
            xs = np.nonzero(a.any(0))[0]
            out.append((s, sp, xs[-1] - xs[0] + 1))
    return out


def _p(root, pack, name):
    return os.path.join(root, pack, name + '.png') if pack else os.path.join(root, name + '.png')


def load(pack, name):
    """src/<pack>/<name>.png → RGBA int32 배열. pack 이 '' 이면 src/<name>.png."""
    return np.array(Image.open(_p(SRC, pack, name)).convert('RGBA')).astype(np.int32)


def save(arr, pack, name):
    dst = _p(OUT, pack, name)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    src = Image.open(_p(SRC, pack, name))
    im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), 'RGBA')
    assert im.size == src.size
    im.save(dst)
    return dst


def edit_boxes(name, cls='clear'):
    """그 그림의 edit 상자 중 분류가 cls 인 것 (clear·bg·design)."""
    c = norm_class(cls)
    return [b for b in boxes(name) if b['kind'] == 'edit' and norm_class(b.get('분류') or b.get('class')) == c]


def sprite_for(fname, rect):
    """상자 안에 든 메타 스프라이트 사각형(가장 큰 것). 없으면 상자."""
    best = None
    for k, sr in meta(fname):
        if inside(sr, rect):
            if best is None or overlap(sr, rect) > overlap(best, rect):
                best = sr
    return best or rect


def clip_of(fname, rect):
    """그릴 수 있는 칸 = 상자 ∩ 스프라이트(게임이 보여 주는 사각형)."""
    s = sprite_for(fname, rect)
    return (max(s[0], rect[0]), max(s[1], rect[1]), min(s[2], rect[2]), min(s[3], rect[3]))


# ---------------------------------------------------------------- 글꼴 고르기 — 원문 충실
# 원문이 도트 글씨(안티에일리어스 없음)면 화소 글꼴, 매끈한 글씨면 벡터 글꼴 — 둘 다 원문 높이에 맞춘다.
# 매끈한 글씨인데 그 높이의 벡터 한글이 뭉개지면 그때만 화소 글꼴. 칸에 안 들어가면 원문 높이에서
# 자간 → 장평(0.9·0.8) → 한 단계 작은 크기 순. 원문 높이의 MIN_RATIO 아래로 줄면 메모에 적는다.
# 뭉개짐 판정 (잠정값, 2026-11-24) — 원문과 견준다:
#   ① 「한」의 잉크 높이가 VEC_MIN_H 화소 미만 (글자 꼴이 안 나온다)
#   ② 그 벡터 글자의 중간 농도(가장자리 화소 중 섞인 색 비율)가 원문의 중간 농도보다 VEC_MID_MARGIN 넘게 높다
#      — 원문보다 더 번진다. 원문도 가는 명조처럼 번져 있으면 같은 정도의 벡터는 뭉개짐이 아니다.
VEC_MIN_H = 10   # 노토 산스 굵은꼴 8·9px(높이 8·9)은 뭉개지고 10px(높이 10)부터 읽힌다
VEC_MID_MARGIN = 0.1
MIN_RATIO = 0.85
INK_MID_MAX = 0.55   # 글자 가장자리의 섞인 색 비율이 이 아래면 도트 글씨로 본다 (잠정값 — 여섯 게임 글씨를 눈으로 보고. 틀릴 수 있어 사용자가 확인, style ink= 로 고침)
_BLUR = {}
_GH = {}


def is_pixel(spec):
    return spec[0] in PIXEL


def glyph_h(spec):
    """그 spec 으로 그린 「한」의 잉크 높이 (화소)."""
    k = tuple(spec[:2])
    if k not in _GH:
        a, _, _ = text_mask('한', spec[:2] if not is_pixel(spec) else spec[:1], 0)
        ys = np.nonzero(a.max(1) >= 0.5)[0]
        _GH[k] = int(ys[-1] - ys[0] + 1) if len(ys) else 0
    return _GH[k]


def vec_mid(text, spec):
    """(한글 잉크 높이, 중간 농도) — 그 spec 으로 그린 글자 가장자리 화소 중 섞인 색(덮임 0.1~0.9)의 비율.
    원문의 중간 농도(ink_kind)와 같은 방법으로 잰다. 화소 글꼴은 (None, 0.0)."""
    if is_pixel(spec):
        return None, 0.0
    k = (text, tuple(spec))
    if k not in _BLUR:
        a, _, _ = text_mask(text.replace(' ', ''), spec, 0)
        ink = a > 0.04
        pad = np.pad(ink, 1)
        edge = ink & ~(pad[:-2, 1:-1] & pad[2:, 1:-1] & pad[1:-1, :-2] & pad[1:-1, 2:])
        mid = float(((a > 0.1) & (a < 0.9))[edge].mean()) if edge.any() else 0.0
        _BLUR[k] = (glyph_h(spec), mid)
    return _BLUR[k]


def blurry(text, spec, orig_mid=None):
    """벡터 spec 으로 그리면 뭉개지나 — 글자 꼴이 안 나오는 높이거나, 원문보다 더 번질 때. 화소 글꼴은 False."""
    if is_pixel(spec):
        return False
    h, mid = vec_mid(text, spec)
    return h < VEC_MIN_H or (orig_mid is not None and mid > orig_mid + VEC_MID_MARGIN)


def measure_grad(orig, bg, rect, min_range=24):
    """원문 글자색이 위아래로 바뀌면 (y위, 색, y아래, 색) — 줄마다 글자 몸통 화소 색의 중앙값을 직선으로 맞춘 것.
    바뀜이 min_range 보다 작으면 None(한 색). bg 가 있으면 원본과 지운 배경의 차이가 큰 화소, 없으면 알파가 큰 화소."""
    x0, y0, x1, y1 = rect
    o = orig[y0:y1, x0:x1].astype(float)
    if bg is not None:
        d = np.abs(o - bg[y0:y1, x0:x1].astype(float))[..., :3].max(2)
        m = d >= 0.6 * d.max() if d.max() > 0 else d > 0
    else:
        m = o[..., 3] >= 0.8 * o[..., 3].max() if o[..., 3].max() > 0 else o[..., 3] > 0
    ys, cs, ws = [], [], []
    for y in range(o.shape[0]):
        if m[y].sum() >= 3:
            ys.append(y0 + y)
            cs.append(np.median(o[y][m[y]][:, :3], 0))
            ws.append(m[y].sum())
    if len(ys) < 3:
        return None
    ys, cs, ws = np.array(ys, float), np.array(cs), np.array(ws, float)
    yt, yb = ys[0], ys[-1]
    fit = [np.polyfit(ys, cs[:, k], 1, w=np.sqrt(ws)) for k in range(3)]
    ct = tuple(int(np.clip(round(np.polyval(f, yt)), 0, 255)) for f in fit)
    cb = tuple(int(np.clip(round(np.polyval(f, yb)), 0, 255)) for f in fit)
    if max(abs(a - b) for a, b in zip(ct, cb)) < min_range:
        return None
    return (int(yt), ct, int(yb), cb)


def ink_kind(orig, bg, rect):
    """원문 글자가 도트 글씨('pixel')인지 매끈한 글씨('smooth')인지, 섞인 색 비율과 함께.
    글자 가장자리 화소 중 주된 색(채움·외곽선 — 글자 화소의 15% 이상인 색, 최대 2개)·바탕(투명 또는 지운 배경의
    그 자리 색)의 어느 것과도 가깝지 않은 화소 = 섞인 색(안티에일리어스)의 비율. 도트 글씨는 거의 없다."""
    x0, y0, x1, y1 = rect
    o = orig[y0:y1, x0:x1].astype(float)
    if bg is None:
        ink = o[..., 3] > 0
        if ink.all():          # 불투명 바탕 위 글씨(투명 글씨로 분류됐어도): 가장 흔한 색을 바탕으로 본다
            q = (o[..., :3] // 8).reshape(-1, 3)
            v, c = np.unique(q, axis=0, return_counts=True)
            bgc = v[c.argmax()] * 8 + 4
            ink = np.abs(o[..., :3] - bgc).max(2) > 24
            back = np.broadcast_to(np.append(bgc, 255), o.shape)
        else:
            back = np.zeros_like(o)
    else:
        b = bg[y0:y1, x0:x1].astype(float)
        ink = np.abs(o - b).max(2) > 24
        back = b
    px = o[ink]
    if len(px) < 8:
        return 'smooth', None
    q = (px // 8).astype(int)
    v, c = np.unique(q, axis=0, return_counts=True)
    dom = [vv * 8 + 4 for vv, cc in sorted(zip(v, c), key=lambda t: -t[1])[:2] if cc >= 0.15 * len(px)]
    near = np.abs(o - back).max(2) <= 24
    for d in dom:
        near |= np.abs(o - d).max(2) <= 24
    # 가장자리(글자 화소 중 바탕과 맞닿은 것)에서만 센다 — 큰 글씨는 속이 넓어 섞인 색 비율이 묽어진다
    pad = np.pad(ink, 1)
    edge = ink & ~(pad[:-2, 1:-1] & pad[2:, 1:-1] & pad[1:-1, :-2] & pad[1:-1, 2:])
    if edge.sum() < 8:
        return 'smooth', None
    mid = float(1 - near[edge].mean())
    return ('pixel' if mid < INK_MID_MAX else 'smooth'), mid


def orig_height(meas, orig, rect, bg=None, mode='alpha'):
    """원문 글자 한 줄의 높이 = 글자 화소가 있는 행이 이어진 가장 긴 구간.
    투명 글씨: 잉크 중 가장 흔한 색(채움색)에 가까운 화소. 배경 글씨: 원본과 지운 배경의 차이가 큰(99 백분위의
    절반 이상) 화소 — Codex 가 바로 옆 영문·무늬까지 손댄 경우 차이 전체로 재면 높이가 부푼다."""
    x0, y0, x1, y1 = rect
    if bg is not None:
        d = np.abs(orig[y0:y1, x0:x1] - bg[y0:y1, x0:x1])[..., :3].max(2).astype(float)
        if not (d > 24).any():
            return 0
        m2 = d >= 0.5 * np.percentile(d[d > 24], 99)
    else:
        m = core_mask(meas, rect, mode)
        if not m.any():
            return 0
        o = orig[y0:y1, x0:x1, :3]
        q = (o[m] // 16).astype(int)
        v, c = np.unique(q, axis=0, return_counts=True)
        fill = v[c.argmax()] * 16 + 8
        m2 = m & (np.abs(o - fill).max(2) <= 48)
    best = run = 0
    for r in m2.any(1):
        run = run + 1 if r else 0
        best = max(best, run)
    return best


def _vec_size_for(key, h):
    """「한」 높이가 h 에 가장 가까운 벡터 크기 (같으면 큰 쪽)."""
    best = None
    for s in range(6, 120):
        g = glyph_h((key, s))
        d = abs(g - h)
        if best is None or d < best[0] or (d == best[0]):
            if best is None or d <= best[0]:
                best = (d, s)
        if g > h + 2:
            break
    return best[1]


def order_key(spec):
    """그려 볼 차례(작을수록 먼저): 벡터 → 화소, 높이 큰 것 → 작은 것, 장평 넓은 것 → 좁은 것."""
    xs = spec[3] if len(spec) > 3 else 1
    return (1 if is_pixel(spec) else 0, -glyph_h(spec), -xs)


def _candidates(st, texts, orig_h, kind, orig_mid=None):
    """(그려 볼 spec 목록, 뭉개져서 뺀 벡터 spec 목록).
    spec=('키', 'orig') 이면 원문 높이에서 시작해 장평 0.9·0.8 → 한 단계 작은 크기 … 로 목록을 만든다.
    fallback 을 직접 주면 그대로. 화소 spec(pixel=)은 원문 높이에 가까운 것부터."""
    specs = st['_specs']
    if len(specs) == 1 and not is_pixel(specs[0]) and specs[0][1] == 'orig':
        key = specs[0][0]
        s0 = _vec_size_for(key, orig_h)
        specs = []
        for s in range(s0, 5, -1):
            specs += [(key, s), (key, s, None, 0.9), (key, s, None, 0.8)]
            if glyph_h((key, s)) < VEC_MIN_H - 2:
                break
    pix = sorted(st.get('_pixel') or [], key=lambda p: (glyph_h(p) > orig_h, abs(glyph_h(p) - orig_h)))
    vec, dropped = [], []
    for sp in specs:
        if pix and any(blurry(t, sp, orig_mid) for t in texts):
            dropped.append(sp)
        else:
            vec.append(sp)
    if kind == 'pixel' and pix:
        return pix + vec, dropped
    return vec + pix, dropped


def fmt(spec):
    s = f'{spec[0]}' + ('' if is_pixel(spec) else f' {spec[1]}')
    if len(spec) > 3 and spec[3] != 1:
        s += f' 장평{spec[3]}'
    return s


# ---------------------------------------------------------------- 공통 실행
def run(pack, name, style_for_box, erase_rect_for_box=None, lines_for_box=None, protect_extra=(), report=print, spill_px=6,
        cls='clear', start=None, floor=None, save_out=True):
    """style_for_box(box) -> dict(spec, align, spacing, color, alpha, outline, glow, shadow, mode, dx, dy, fallback=[spec..],
    pixel=[화소 spec..], ink='auto'|'pixel'|'smooth')
      spec=('키', 'orig') — 원문 높이에 맞춘 벡터 크기에서 시작 (권장). 숫자를 주면 그 크기부터 fallback 순.
      pixel= — 원문이 도트 글씨이거나, 벡터가 뭉개질 때 쓸 화소 글꼴들. ink= — 원문 판정을 사람이 정할 때.
      h= — 원문 글자 높이를 사람이 정할 때 (재는 값이 틀릴 때).
    floor = {묶음 키: spec} — 계열 통일(run_series)이 정한 글꼴·크기. 이 spec 보다 앞 차례는 건너뛴다.
    돌려주는 값: (경로, 메모, {묶음 키: dict(h=원문 높이, spec=고른 spec)}).
    lines_for_box(box) -> [(text, align)…] (없으면 ko 를 「\n」(격자 파일에 적은 두 글자)에서 나눈 줄들). 원본 줄 수와 같아야 한다."""
    floor = floor or {}
    fname = name + '.png'
    if not lines_for_box:
        blank = [b['id'] for b in edit_boxes(name, cls) if not (b.get('ko') or '').strip()]
        if blank:
            raise SystemExit(f'imgrender: {name} 의 상자 {", ".join(blank)} 에 ko 가 비었다 — 번역문을 먼저 정한다 (img.py imgreq)')
    orig = load(pack, name)
    # 배경 글씨(bg): 지운 배경(start 폴더, imgcodex 통과분)에서 시작하고, 줄 위치는 원본에서 잰다. 지우기는 하지 않는다.
    arr = (np.array(Image.open(os.path.join(start, (pack + '/' if pack else '') + fname)).convert('RGBA')).astype(np.int32)
           if start else orig.copy())
    bg0 = arr.copy() if start else None
    # 잉크를 잴 그림: 투명 글씨는 원본 그대로. 배경 글씨는 원본과 지운 배경이 다른 화소만 남긴 것 —
    # 원본에서 바로 재면 뒤의 판·무늬까지 글자로 잡힌다.
    meas = orig
    if start:
        meas = orig.copy()
        meas[..., 3] = np.where(np.abs(orig - arr).max(2) > 24, orig[..., 3], 0)
    bx = edit_boxes(name, cls)
    rects = [(erase_rect_for_box(b) if erase_rect_for_box else b['rect']) for b in bx]
    # 'auto' 색: 원본 글자 잉크(알파×밝기)의 90 백분위 — 화소 글꼴(1px 획, 안티에일리어스 없음)이 원본보다 밝아 보이지 않게
    vals = []
    for b, er in zip(bx, rects):
        s = meas[er[1]:er[3], er[0]:er[2]].astype(float)
        v = s[..., 3] / 255 * s[..., :3].mean(2)
        vals.extend(v[v > 20].tolist())
    auto = int(np.percentile(vals, 90)) if vals else 255
    # 원본 줄 위치는 지우기 전에 잰다
    plan = []
    for b, er in zip(bx, rects):
        st = dict(style_for_box(b))
        if st.get('color') == 'auto':
            st['color'] = (auto, auto, auto)
        lines = lines_for_box(b) if lines_for_box else [(t, st.get('align', 'left')) for t in b['ko'].split(NL)]
        meas_rect = st.pop('measure', None) or clip_of(fname, er)
        ol = lines_of(meas, meas_rect, len(lines), st.pop('mode', 'bright'))
        if st.get('grad') == 'auto':      # 원문 글자색 세로 그러데이션을 재서 쓴다 (없으면 한 색)
            st['grad'] = measure_grad(orig, bg0, er)
            if st['grad'] and not st.get('color'):
                st['color'] = st['grad'][1]
        ink = st.pop('ink', 'auto')
        st['_ink'] = (ink, None) if ink != 'auto' else ink_kind(orig, bg0, er)
        h = st.pop('h', None)
        if not h:
            h = orig_height(meas, orig, meas_rect, bg0)
            if st.get('outline'):      # 잰 높이에는 원문 외곽선이 들어 있다 — 우리도 외곽선을 두르므로 몸통만
                h -= 2 * int(round(st['outline'][0]))
        st['_h'] = h
        plan.append((b, st, lines, ol, clip_of(fname, er) if 'clip' not in st else st.pop('clip')))
    if not start:
        keep = [b['rect'] for b in boxes(name) if b['kind'] == 'keep']   # keep 상자는 늘 지킨다
        erase(arr, name, fname, rects, list(protect_extra) + keep, spill_px)
    notes = []
    for b, st, lines, ol, clip in plan:
        st['_specs'] = [st.pop('spec')] + st.pop('fallback', [])
        px = st.pop('pixel', None) or []
        st['_pixel'] = [px] if px and isinstance(px[0], str) else list(px)
        st['_spacings'] = st.pop('spacings', [st.pop('spacing', 0)])
        st.pop('align', None)

    # 짝(선택/비선택): '_lead': 키 인 상자를 먼저 그리고, '_follow': 같은 키 인 상자는 그 글자 모양(gl)을 그대로
    # 스프라이트 가운데('_center') 기준 같은 자리에 얹는다(효과만 다르게). 결과 자리는 pair_log 에.
    pairs = {}
    pair_log = {}

    def draw(target, b, st, lines, ol, clip, spec, sp):
        extra = {k: v for k, v in st.items() if not k.startswith('_')}
        dxl = extra.pop('dx_lines', None)
        for i, ((txt, al), ln) in enumerate(zip(lines, ol)):
            e2 = dict(extra)
            if dxl:
                e2['dx'] = e2.get('dx', 0) + dxl[i]
            if '_follow' in st:
                if st['_follow'] not in pairs:
                    raise ValueError('짝의 앞(선택)을 못 그림')
                g = pairs[st['_follow']]
                cx, cy = st['_center']
                x, y = int(round(cx + g['rx'])), int(round(cy + g['ry']))
                e2.pop('dx', None), e2.pop('dy', None)
                compose(target, g['gl'], x, y, clip=clip, char_idx=g['ci'], **e2)
                pair_log[st['_follow']] = pair_log.get(st['_follow'], {}) | {'o': (x - cx, y - cy)}
                continue
            r = place(target, txt, spec, ln, al, clip, spacing=sp, **e2)
            if '_lead' in st:
                cx, cy = st['_center']
                pairs[st['_lead']] = dict(gl=r['gl'], ci=r['ci'], rx=r['x'] - cx, ry=r['y'] - cy)
                pair_log[st['_lead']] = {'t': (r['x'] - cx, r['y'] - cy)}

    # 같은 그림의 같은 글꼴 묶음(group)은 모두 들어가는 가장 큰 조합 하나로
    groups = {}
    for p in plan:
        groups.setdefault(p[1].get('_group') or 'box:' + str(p[0]['id']), []).append(p)
    info = {}
    for g, items in groups.items():
        items.sort(key=lambda p: 0 if '_lead' in p[1] else 1)   # 짝의 앞(선택)을 먼저
        st0 = items[0][1]
        chosen = None
        why = ''
        hs = sorted(p[1]['_h'] for p in items)
        orig_h = hs[len(hs) // 2]     # 묶음은 원문 크기가 같다 — 잰 값의 가운데(둘이면 큰 쪽)
        kind, mid = st0['_ink']
        mids = sorted(p[1]['_ink'][1] for p in items if p[1]['_ink'][1] is not None)
        gmid = mids[len(mids) // 2] if mids else None   # 묶음 원문의 중간 농도 — 가운데 값
        gspecs, dropped = _candidates(st0, [t for p in items for t, _ in p[2]], orig_h, kind, gmid)
        if g in floor:
            fk = order_key(floor[g])
            gspecs = [s for s in gspecs if order_key(s) >= fk]
        if st0.get('_sp_each'):
            # 크기는 묶음 전체 하나, 자간은 상자(짝은 짝째로)마다 들어가는 가장 넓은 것
            units = {}
            for p in items:
                units.setdefault(p[1].get('_lead') or p[1].get('_follow') or id(p), []).append(p)
            for spec in gspecs:
                trial = arr.copy()
                used = []
                for un in units.values():
                    ok = False
                    for sp in st0['_spacings']:
                        t2 = trial.copy()
                        try:
                            for (b, st, lines, ol, clip) in un:
                                draw(t2, b, st, lines, ol, clip, spec, sp)
                        except ValueError as e:
                            why = f"{b['id']} {e}"
                            continue
                        trial = t2
                        used.append(','.join(b['id'] for b, *_ in un) + f' 자간{sp}')
                        ok = True
                        break
                    if not ok:
                        break
                else:
                    chosen = (spec, ' / '.join(used), trial)
                    break
        for spec in ([] if st0.get('_sp_each') else gspecs):
            for sp in st0['_spacings']:
                trial = arr.copy()
                try:
                    for (b, st, lines, ol, clip) in items:
                        draw(trial, b, st, lines, ol, clip, spec, sp)
                except ValueError as e:
                    why = f"{b['id']} {e}"
                    continue
                chosen = (spec, sp, trial)
                break
            if chosen:
                break

        def why_note(spec):
            src = f"원문 {orig_h}px " + ('도트' if kind == 'pixel' else '매끈') + (f'(중간 농도 {mid:.2f})' if mid is not None else '(지정)')
            h = glyph_h(spec)
            out = f"{src} → {fmt(spec)} {h}px"
            if is_pixel(spec) and kind != 'pixel':
                out += (' — 벡터 ' + ','.join(str(x) for x in sorted({d[1] for d in dropped}, reverse=True)[:3]) + 'px 뭉개짐') if dropped else ' — 벡터가 칸에 안 들어감'
            if h < orig_h * MIN_RATIO:
                out += f' ※ 원문의 {h / orig_h:.0%}'
            if g in floor:
                out += ' (계열 통일)'
            return out
        if chosen:
            arr[:] = chosen[2]
            info[g] = dict(h=orig_h, spec=chosen[0])
            notes.append(','.join(b['id'] for b, *_ in items) + f': {why_note(chosen[0])} 자간{chosen[1]}')
        else:
            # 묶음이 안 되면 상자마다
            for (b, st, lines, ol, clip) in items:
                ok = False
                bh = st['_h']
                for spec in _candidates(st, [t for t, _ in lines], bh, kind)[0]:
                    for sp in st['_spacings']:
                        trial = arr.copy()
                        try:
                            draw(trial, b, st, lines, ol, clip, spec, sp)
                        except ValueError as e:
                            why = str(e)
                            continue
                        arr[:] = trial
                        ok = True
                        info.setdefault(g, dict(h=orig_h, spec=spec))
                        if order_key(spec) > order_key(info[g]['spec']):
                            info[g]['spec'] = spec
                        notes.append(f"{b['id']}: {why_note(spec)} 자간{sp} (묶음과 다름)")
                        break
                    if ok:
                        break
                if not ok:
                    notes.append(f"{b['id']} {b['ko']!r}: 칸에 안 들어감 — {why}")
    if not save_out:
        return None, notes, info
    p = save(arr, pack, name)
    report(f'{name}: ' + '\n  '.join([''] + notes))
    for k, v in pair_log.items():
        report(f'  짝 {k}: 스프라이트 가운데 기준 글자 왼위 t{v.get("t")} o{v.get("o")}')
    return p, notes, info


def run_series(pack, names, style_for_box, report=print, same_px=1, **kw):
    """한 계열(같은 모양의 그림 묶음)에서 원문 크기가 같은 글씨를 같은 글꼴·같은 크기로 그린다.
    1차: 그림마다 저장 없이 그려 보고 묶음 키(_group 또는 'box:<id>')별로 원문 높이와 고른 글꼴·크기를 모은다.
    같은 키이고 원문 높이 차이가 same_px 안이면, 그 그림들에서 고른 것 중 가장 뒤 차례(가장 작은 것)로 맞춘다
    — 모든 그림의 칸에 들어가는 가장 큰 것. 원문 높이가 다르면 맞추지 않는다.
    2차: 그렇게 정해 저장한다."""
    first = {}
    for n in names:
        first[n] = run(pack, n, style_for_box, report=lambda *a: None, save_out=False, **kw)[2]
    byg = {}
    for n, info in first.items():
        for g, v in info.items():
            byg.setdefault(g, []).append((n, v))
    floor = {}
    for g, vs in byg.items():
        if len(vs) < 2:
            continue
        hs = [v['h'] for _, v in vs]
        if max(hs) - min(hs) > same_px:
            report(f'계열: 묶음 {g} 원문 높이가 그림마다 다름 {min(hs)}~{max(hs)}px — 크기를 맞추지 않음')
            continue
        worst = max((v['spec'] for _, v in vs), key=order_key)
        if any(v['spec'] != worst for _, v in vs):
            floor[g] = worst
            report(f'계열: 묶음 {g} ({len(vs)}장, 원문 {min(hs)}~{max(hs)}px) → 모두 {fmt(worst)}')
    return [run(pack, n, style_for_box, report=report, floor=floor, **kw) for n in names]
