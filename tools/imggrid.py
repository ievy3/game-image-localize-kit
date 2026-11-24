"""그림 격자·정본 묶음 — 사용자·외부 편집 도구에 그림 수정을 맡길 때 넘기는 꾸러미를 만든다.

    img.py imggrid --spec <grids 폴더 | 정본.csv | 정본.py> --src src --out bundles/<이름>
                   [--class clear|bg|design] [--title "튜토리얼 그림 — 일본어를 한국어로"] [--mistakes 지난번.txt] [--keep "TUTORIAL,START SKIP"]
                   [--scale auto|3] [--force] [--erase-only]
    → <out>/orig/(원본 그대로) · <out>/grid/<이름>_grid.png · <out>/지시사항.txt · <out>/정본.csv · <out>/상자.csv + <out>.zip
      결과는 <out>/result/ 에 원본과 같은 이름으로 받는다(지시문에 적힘). 상자.csv = 번호 상자(edit)·회색 상자(keep), imgbox·imgcodex 가 읽는다.

정본 입력(둘 중 하나):
    .csv  열 file, x0, y0, x1, y1, ja(또는 jp), ko[, note, kind] — imgbox 상자 CSV 에 ja·ko 열을 더한 것.
          kind=keep 행은 번호 없이 회색 상자로만 그린다(그대로 둘 글자). 다른 열은 무시.
    .py   SPEC = {'그림.png': [((x0, y0, x1, y1), '일본어', '한국어', '비고'), ...], ...}
          있으면 BUNDLE_TITLE(지시문 첫 줄) · MISTAKES(「지난번에 틀린 것」 문자열) · KEEP(그대로 둘 영문 목록)도 읽는다.
    좌표는 원본 그림 픽셀, x1·y1 은 들어가지 않는다(폭 = x1 - x0, imgbox 와 같다).

격자 그림: 원본을 배율(기본 auto — 긴 변이 약 1500px, 2~8배)로 키우고 10px 옅은 격자 · 50px 굵은 선과 좌표 숫자,
    번호 붙은 빨간 상자. 투명 칸은 어두운 바탕(40,40,48)에 합성해 보이게 한다. 번호 = 정본.csv 의 no.
지시문: 키트 기본 「반드시 지킬 것」 8개 + (주면) 그대로 둘 영문 목록 · 「지난번에 틀린 것」 · 그림마다 번호·좌표·일본어 → 한국어.
--erase-only: 배경 글씨(bg) 요청 — 「글자를 지운 배경만」 (--class bg 면 저절로 켜진다). 한국어 칸(ko)이 없어도 되고, 지시문에 한국어를 쓰라는 규칙이 없다.
코덱스에 맡기기·2차 점검·기계 검사는 `img.py imgcodex <out>`.
받은 결과는 `img.py imgview` 로 원본과 나란히 눈으로 판정한다. `img.py imgbox --boxes <out>/정본.csv` 는 바뀐 곳 지도로만(합격 조건 아님).
"""
import _utf8  # noqa: F401  (출력 UTF-8)
import argparse
import csv
import importlib.util
import os
import shutil
import sys
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

COLS = ['file', 'no', 'x0', 'y0', 'x1', 'y1', 'ja', 'ko', 'note']
BG = (40, 40, 48, 255)
RESULT_DIR = 'result'
ERASE_MARK = '글자를 지운 배경만 만든다'      # imgcodex 가 배경 글씨(bg) 꾸러미를 알아보는 표시 (RULES_ERASE 첫 줄)
FONT_REL = 'Pretendard/Pretendard-Bold.otf'

RULES = """[반드시 지킬 것]
1. 아래 표(정본.csv 와 같음)의 한국어를 글자 하나 바꾸지 말고 그대로 쓴다. 다른 말로 옮기지 않는다(이름·용어 포함).
2. 자리는 원본 픽셀 좌표 (x0,y0)-(x1,y1), x1·y1 은 상자 밖. grid/ 그림은 원본을 {scale_note} 키운 위에
   10픽셀 격자(굵은 선·숫자 = 50픽셀)와 번호 붙은 빨간 상자를 그린 것 — 번호가 표의 번호다. 회색 상자는 그대로 둘 글자.
3. 상자 안 일본어는 남김없이 지운다. 획 조각·번진 자국·검은 덩어리가 남으면 안 된다.
4. 일본어는 상자 밖으로 넘친 획·외곽선·그림자까지 남김없이 지운다. 일본어와 상관없는 그림·아이콘·영문·숫자는 바꾸지 않는다.
5. 그대로 두는 것: 영문, 숫자, ★☆ 같은 기호, ○□△× 같은 아이콘 모양, 이름 끝 영문 A·B·C.
   이름 끝 A·B·C 는 원본 글자를 그대로 두고 앞의 가나만 한국어로 바꾼다(새로 쓰지 않는다).{keep}
6. 글자 모양은 원본 그 자리와 같게: 같은 색(그라데이션·강조색 포함), 같은 외곽선·발광, 같은 높이,
   같은 정렬(가운데·왼쪽·오른쪽), 같은 기울임. 글꼴은 원본과 비슷한 것으로.
7. 한 줄이 상자 폭을 넘으면 자간을 조금 좁히거나 글자를 조금 줄인다. 잘리거나 두 줄로 나뉘면 안 된다.
8. 순서·줄 바꿈은 표 그대로(능력치·메뉴·단추 설명의 순서를 바꾸지 않는다).
"""

RULES_ERASE = """[반드시 지킬 것 — 글자를 지운 배경만 만든다. 한국어는 쓰지 않는다]
1. 표의 번호 상자 안 일본어를 지우고, 그 자리는 글자 뒤에 있었을 배경(무늬·그라데이션·테두리)으로 이어 채운다.
2. 자리는 원본 픽셀 좌표 (x0,y0)-(x1,y1), x1·y1 은 상자 밖. grid/ 그림은 원본을 {scale_note} 키운 위에
   10픽셀 격자(굵은 선·숫자 = 50픽셀)와 번호 붙은 빨간 상자를 그린 것 — 번호가 표의 번호다. 회색 상자는 그대로 둘 글자.
3. 획 조각·번진 자국·외곽선·그림자·글자 모양의 얼룩이 남으면 안 된다. 상자 밖으로 넘친 획까지 지운다.
4. 일본어와 상관없는 그림·아이콘·영문·숫자·테두리는 바꾸지 않는다. 상자 밖은 넘친 일본어 자국만 지우고 나머지는 원본 화소 그대로.
5. 그대로 두는 것: 영문, 숫자, ★☆ 같은 기호, ○□△× 같은 아이콘 모양.{keep}
6. 한국어나 다른 글자를 새로 쓰지 않는다. 빈 자리는 비워 둔다(한글은 키트가 따로 렌더한다).
"""


def _font(size):
    here = Path(__file__).resolve().parent
    roots = [here.parent / 'fonts']                       # 키트의 fonts/ (FONTS.md — 없으면 기본 글꼴)
    if os.environ.get('IMGKIT_FONTS'):
        roots.insert(0, Path(os.environ['IMGKIT_FONTS']))
    for r in roots:
        if (r / FONT_REL).is_file():
            return ImageFont.truetype(str(r / FONT_REL), size)
    return ImageFont.load_default(size=size)


def load_spec(path, erase_only=False, classes=None):
    """→ (spec, meta). spec = {file: [((x0,y0,x1,y1), ja, ko, note, kind)]}, meta = {title, mistakes, keep}.
    path 가 폴더면 안의 *.csv(격자 파일 BOXES_*.csv)를 모두 읽는다. classes 를 주면 「분류」 열이 그 값인 edit 행만
    (keep 행은 늘 넣는다 — 그대로 둘 글자를 회색 상자로 보여야 한다). 고른 edit 행이 없는 그림은 뺀다."""
    p = Path(path)
    if p.is_dir() or classes:
        files = sorted(p.glob('*.csv')) if p.is_dir() else [p]
        spec, meta = {}, {}
        for f in files:
            s1, m1 = load_spec(f, erase_only=True)
            rows = _rows_by_class(f, classes) if classes else None
            for name, items in s1.items():
                keep = [it for it in items if it[4] == 'keep']
                edit = [it for it in items if it[4] != 'keep' and (rows is None or (name, it[0]) in rows)]
                if edit:
                    spec.setdefault(name, []).extend(edit + keep)
            meta = meta or m1
        if not erase_only:
            for name, items in spec.items():
                for box, _ja, ko, _n, kind in items:
                    if kind == 'edit' and not ko.strip():
                        raise SystemExit(f'imggrid: {name} {box} 에 ko 가 비었다 — 정본 한국어 없이 넘기지 않는다')
        return spec, meta
    spec, meta = {}, {}
    if p.suffix.lower() == '.py':
        sp = importlib.util.spec_from_file_location('_imggrid_spec', p)
        mod = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(mod)
        for name, items in mod.SPEC.items():
            spec[name] = [(tuple(int(v) for v in it[0]), it[1], it[2], it[3] if len(it) > 3 else '', 'edit') for it in items]
        meta = {'title': getattr(mod, 'BUNDLE_TITLE', ''), 'mistakes': getattr(mod, 'MISTAKES', ''), 'keep': list(getattr(mod, 'KEEP', []))}
        return spec, meta
    with open(p, encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            name = (r.get('file') or '').replace('\\', '/').strip()
            if not name:
                continue
            box = tuple(int(float(r[k])) for k in ('x0', 'y0', 'x1', 'y1'))
            kind = (r.get('kind') or 'edit').strip().lower()
            ja = r.get('ja') or r.get('jp') or ''
            ko = r.get('ko') or ''
            if kind == 'edit' and not ko.strip() and not erase_only:
                raise SystemExit(f'imggrid: {p} 의 {name} {box} 에 ko 가 비었다 — 정본 한국어 없이 넘기지 않는다')
            spec.setdefault(name, []).append((box, ja, ko, r.get('note') or '', kind))
    return spec, meta


# 갈래 이름은 이 넷뿐이다
CLASSES = ('clear', 'bg', 'design', 'keep')


def norm_class(c):
    c = (c or '').strip().lower()
    if c and c not in CLASSES:
        raise SystemExit(f'분류 「{c}」 — clear · bg · design · keep 중 하나로 적는다')
    return c


def _rows_by_class(path, classes):
    """{(file, box)} — 「분류」(또는 class) 열이 classes 안인 행."""
    out = set()
    with open(path, encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            c = (r.get('분류') or r.get('class') or '').strip()
            if norm_class(c) in classes:
                name = (r.get('file') or '').replace('\\', '/').strip()
                out.add((name, tuple(int(float(r[k])) for k in ('x0', 'y0', 'x1', 'y1'))))
    return out


def auto_scale(w, h):
    return max(2, min(8, round(1500 / max(w, h))))


def grid_image(img, items, z):
    """img(RGBA) · items → 격자 그림(RGB). edit 상자는 1부터 번호, keep 상자는 번호 없이 회색."""
    w, h = img.size
    bg = Image.new('RGBA', img.size, BG)
    bg.alpha_composite(img)
    big = bg.convert('RGB').resize((w * z, h * z), Image.NEAREST)
    d = ImageDraw.Draw(big, 'RGBA')
    f = _font(13)
    for x in range(0, w + 1, 10):
        d.line([(x * z, 0), (x * z, h * z)], fill=(255, 255, 255, 110 if x % 50 == 0 else 35), width=1)
    for y in range(0, h + 1, 10):
        d.line([(0, y * z), (w * z, y * z)], fill=(255, 255, 255, 110 if y % 50 == 0 else 35), width=1)
    for x in range(0, w, 50):
        d.text((x * z + 2, 1), str(x), font=f, fill=(255, 255, 0, 255), stroke_width=2, stroke_fill=(0, 0, 0, 255))
    for y in range(50, h, 50):
        d.text((2, y * z + 1), str(y), font=f, fill=(0, 255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0, 255))
    no = 0
    for (x0, y0, x1, y1), _ja, _ko, _note, kind in items:
        rect = [x0 * z, y0 * z, x1 * z - 1, y1 * z - 1]
        if kind == 'keep':
            d.rectangle(rect, outline=(170, 170, 170, 255), width=2)
            continue
        no += 1
        d.rectangle(rect, outline=(255, 40, 40, 255), width=2)
        d.text((x0 * z + 2, y0 * z + 1), str(no), font=f, fill=(255, 255, 255, 255), stroke_width=2, stroke_fill=(200, 0, 0, 255))
    return big


def _has_alpha(im):
    return im.mode in ('RGBA', 'LA', 'PA') or (im.mode == 'P' and 'transparency' in im.info)


def really_transparent(im):
    """알파 채널이 있고 실제로 255 미만인 화소가 있다. 채널만 있고 다 불투명한 그림(튜토리얼 등)은 불투명으로 다룬다
    — 「투명도 유지」를 적으면 편집 도구가 그림을 이상하게 그린다(사용자 2026-11-18)."""
    return _has_alpha(im) and im.convert('RGBA').getchannel('A').getextrema()[0] < 255


def build(spec, src, out, meta=None, scale='auto', force=False, erase_only=False):
    """묶음 폴더 + 같은 이름 .zip. → (그림 수, 정본 행 수, zip 경로)."""
    meta = meta or {}
    src, out = Path(src), Path(out)
    if out.exists():
        if any(out.iterdir()) and not (out / '정본.csv').is_file() and not force:
            raise SystemExit(f'imggrid: {out} 은 비어 있지 않고 묶음 폴더도 아니다 — 다른 폴더를 주거나 --force')
        shutil.rmtree(out)
    (out / 'orig').mkdir(parents=True)
    (out / 'grid').mkdir()
    rows, body, boxes = [], [], []
    any_alpha = False
    scales = set()
    for name, items in spec.items():
        sp = src / name
        if not sp.is_file():
            sp = src / Path(name).name
        if not sp.is_file():
            raise SystemExit(f'imggrid: 원본 없음: {src / name}')
        im = Image.open(sp)
        w, h = im.size
        for box, *_ in items:
            x0, y0, x1, y1 = box
            if not (0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h):
                raise SystemExit(f'imggrid: {name} 의 상자 {box} 가 그림({w}×{h}) 밖이거나 비었다')
        z = auto_scale(w, h) if scale == 'auto' else int(scale)
        scales.add(z)
        dst = out / 'orig' / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(sp, dst)
        gname = Path(name).with_name(Path(name).stem + '_grid.png').as_posix()
        gp = out / 'grid' / gname
        gp.parent.mkdir(parents=True, exist_ok=True)
        grid_image(im.convert('RGBA'), items, z).save(gp)
        tr = really_transparent(im)
        any_alpha |= tr
        alpha = '투명한 곳 있음(투명도 원본 그대로 유지)' if tr else '불투명 그림(투명도 신경 쓰지 말 것)'
        body.append(f'\n■ {name}  {w}×{h} · {alpha} · 격자 {z}배 (grid/{gname})')
        no = 0
        for box, ja, ko, note, kind in items:
            boxes.append(dict(file=name, x0=box[0], y0=box[1], x1=box[2], y1=box[3], kind='keep' if kind == 'keep' else 'edit'))
            if kind == 'keep':
                body.append(f'    회색 ({box[0]},{box[1]})-({box[2]},{box[3]})  {ja or ko}  — 그대로 둠')
                continue
            no += 1
            rows.append(dict(file=name, no=no, x0=box[0], y0=box[1], x1=box[2], y1=box[3], ja=ja, ko=ko, note=note))
            line = f'{ja}  → 지우기만' if erase_only else f'{ja}  →  {ko}'
            body.append(f'{no:>2}. ({box[0]},{box[1]})-({box[2]},{box[3]})  {line}' + (f'\n      {note}' if note else ''))
    scale_note = f'{scales.pop()}배로' if len(scales) == 1 else '그림마다 적은 배율로'
    keep = meta.get('keep') or []
    keep_line = f'\n   이 묶음에서 그대로 둘 영문: {"·".join(keep)}' if keep else ''
    default_title = f'그림 {len(spec)}장 — 일본어 글자를 지운 배경만 (한국어는 쓰지 않음)' if erase_only else f'그림 {len(spec)}장 — 일본어를 한국어로 바꾸는 작업 지시'
    head = [meta.get('title') or default_title, '',
            '[넘길 것]',
            '- orig/ 의 원본과 같은 이름·같은 크기·같은 형식 PNG' + ('(투명한 곳이 있는 그림은 투명도도 원본 그대로).' if any_alpha else '.'),
            '- 앞에 orig_·current_·clean_ 같은 접두어를 붙이지 말 것.',
            f'- 결과는 이 폴더의 {RESULT_DIR}/ 에 저장한다(orig/ 와 같은 이름·같은 하위 폴더).', '',
            (RULES_ERASE if erase_only else RULES).format(scale_note=scale_note, keep=keep_line).rstrip()]
    mistakes = (meta.get('mistakes') or '').strip()
    if mistakes:
        head += ['', '[지난번에 틀린 것 — 다시 나오면 안 됨]', mistakes]
    with open(out / '지시사항.txt', 'w', encoding='utf-8-sig') as fo:
        fo.write('\n'.join(head + body) + '\n')
    with open(out / '정본.csv', 'w', encoding='utf-8-sig', newline='') as fo:
        wr = csv.DictWriter(fo, COLS)
        wr.writeheader()
        wr.writerows(rows)
    with open(out / '상자.csv', 'w', encoding='utf-8-sig', newline='') as fo:
        wr = csv.DictWriter(fo, ['file', 'x0', 'y0', 'x1', 'y1', 'kind'])
        wr.writeheader()
        wr.writerows(boxes)
    zp = out.with_name(out.name + '.zip')
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in sorted(out.rglob('*')):
            if p.is_file():
                z.write(p, p.relative_to(out).as_posix())
    return len(spec), len(rows), zp


def main(argv=None):
    ap = argparse.ArgumentParser(prog='imggrid', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--spec', required=True, help='정본 .csv(file,x0,y0,x1,y1,ja,ko[,note,kind,분류]) · 그런 .csv 가 든 폴더(grids/) · .py(SPEC)')
    ap.add_argument('--class', dest='classes', help='「분류」 열로 고르기, 쉼표로 — clear(투명 글씨) · bg(배경 글씨) · design(디자인 글씨). 고른 상자가 없는 그림은 빠진다')
    ap.add_argument('--src', required=True, help='원본 그림 폴더')
    ap.add_argument('--out', required=True, help='묶음 폴더(같은 이름 .zip 도 만든다)')
    ap.add_argument('--title', help='지시문 첫 줄')
    ap.add_argument('--mistakes', help='「지난번에 틀린 것」 글 파일(UTF-8)')
    ap.add_argument('--keep', help='그대로 둘 영문, 쉼표로 (예: "TUTORIAL,START SKIP")')
    ap.add_argument('--scale', default='auto', help='격자 그림 배율 (auto = 긴 변 약 1500px, 2~8배)')
    ap.add_argument('--force', action='store_true', help='--out 이 묶음 폴더가 아니어도 지우고 만든다')
    ap.add_argument('--erase-only', action='store_true', help='배경 글씨 요청: 글자를 지운 배경만 — ko 없어도 되고 지시문에 한국어 규칙이 없다 (--class bg 면 저절로)')
    a = ap.parse_args(argv)
    classes = {norm_class(c) for c in a.classes.split(',') if c.strip()} if a.classes else None
    if classes == {'bg'} and not a.erase_only:
        a.erase_only = True
        print('imggrid: --class bg — 글자를 지운 배경만 맡기는 꾸러미로 만든다 (--erase-only)')
    spec, meta = load_spec(a.spec, a.erase_only, classes)
    if not spec:
        raise SystemExit(f'imggrid: {a.spec} 에 정본 행이 없다')
    if a.title:
        meta['title'] = a.title
    if a.mistakes:
        meta['mistakes'] = Path(a.mistakes).read_text(encoding='utf-8-sig')
    if a.keep:
        meta['keep'] = [k.strip() for k in a.keep.split(',') if k.strip()]
    n, rows, zp = build(spec, a.src, a.out, meta, a.scale, a.force, a.erase_only)
    print(f'imggrid: 그림 {n}장 · 정본 {rows}곳 → {zp}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
