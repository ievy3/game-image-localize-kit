"""그림 재검 대조표 — 어두운 바탕에 깔아 흰 글자·투명 바탕 그림을 보이게 한다.

    img.py imgdark --src 원본폴더 --out 대조표폴더 [--skip 끝난그림폴더]

흰 글자 + 투명 바탕 그림은 흰 바탕 뷰어에서 「빈 그림」으로 보인다. 34.Shining Blade 는 이 때문에
결과 화면·상점 등 일본어 그림 21장을 「글자 없음」으로 넘겨 첫 꾸러미까지 갔다(2026-10-30).
그림 분류를 끝낸 뒤, 그대로 둘 그림을 이 대조표로 한 번 더 본다. 불투명 그림·거의 빈 그림은 뺀다.
"""
import _utf8  # noqa: F401  (출력 UTF-8)
import argparse
import hashlib
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

BG = (18, 18, 44)
PAGE = (1500, 1100)


def pick(src, skip):
    seen, out = set(), []
    for p in sorted(Path(src).rglob('*.png')):
        if p.name in skip:
            continue
        im = Image.open(p).convert('RGBA')
        a = np.array(im)
        h = hashlib.sha1(a.tobytes()).hexdigest()
        if h in seen:
            continue
        seen.add(h)
        alpha = a[..., 3]
        if alpha.min() >= 250 or (alpha > 64).mean() < 0.002 or max(im.size) < 16:
            continue
        out.append((p.name, im))
    return sorted(out, key=lambda t: (-t[1].height, t[0]))


def sheets(items, out):
    W, H = PAGE
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    page, x, y, rh = 0, 0, 0, 0
    pg = Image.new('RGB', PAGE, BG)
    d = ImageDraw.Draw(pg)
    for name, im in items:
        s = 2 if im.width <= 128 and im.height <= 64 else 1
        t = im.resize((im.width * s, im.height * s), Image.NEAREST)
        if t.width > W or t.height + 14 > H:
            t = t.resize((min(W, t.width), min(H - 14, t.height)))
        if x + t.width + 4 > W:
            x, y, rh = 0, y + rh + 14, 0
        if y + t.height + 14 > H:
            pg.save(out / f'dark_{page:02d}.png')
            page, x, y, rh = page + 1, 0, 0, 0
            pg = Image.new('RGB', PAGE, BG)
            d = ImageDraw.Draw(pg)
        bg = Image.new('RGBA', t.size, BG + (255,))
        bg.alpha_composite(t)
        pg.paste(bg.convert('RGB'), (x, y + 11))
        d.text((x, y), name[:max(4, t.width // 6 + 4)], fill=(255, 255, 0))
        x, rh = x + t.width + 6, max(rh, t.height)
    pg.save(out / f'dark_{page:02d}.png')
    return page + 1


def main(argv=None):
    ap = argparse.ArgumentParser(prog='img.py imgdark', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--src', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--skip', help='이미 고친 그림 폴더 — 같은 이름은 뺀다')
    a = ap.parse_args(argv)
    skip = {p.name for p in Path(a.skip).rglob('*.png')} if a.skip else set()
    items = pick(a.src, skip)
    if not items:
        print('볼 그림 없음')
        return 0
    n = sheets(items, a.out)
    print(f'그림 {len(items)}장 → 대조표 {n}쪽 {a.out} — 모든 쪽을 눈으로 본다')
    return 0


if __name__ == '__main__':
    sys.exit(main())
