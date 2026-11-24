"""imgreq — 번역 요청표. 격자 파일(grids/)의 일본어를 표 하나로 뽑고, 채워 온 한국어를 격자 파일에 넣는다.

    img.py imgreq --grids grids --out 번역요청.csv           # 요청표 만들기
    img.py imgreq --grids grids --apply 번역요청.csv         # 채운 ko 를 격자 파일에 넣기
    img.py imgreq --grids grids --check                      # ko 가 빈 상자만 보기

요청표 열: file, id, 분류, jp, 칸폭, 칸높이, 원문글자수, note, ko
  - keep 상자는 빼고, edit 상자만 (그림 · 상자 순서 그대로).
  - 격자 파일에 이미 ko 가 있으면 그 값을 넣어 둔다 (고칠 것만 고쳐 돌려주면 된다).
  - 칸폭·칸높이는 상자 크기(px), 원문글자수는 일본어 글자 수 — 번역자가 길이를 가늠하는 참고값.
번역은 사용자가 주거나(요청본), 세션이 채운 뒤 사용자가 승인한다 — 어느 쪽인지는 작업 시작 때 사용자에게 묻는다.
--apply 는 (file, id) 로 맞춰 ko 칸만 바꾼다. 맞는 상자가 없는 행은 알리고 끝 코드 1.
"""
import _utf8  # noqa: F401  (출력 UTF-8)
import argparse
import csv
import sys
from pathlib import Path

from imggrid import norm_class

COLS = ['file', 'id', '분류', 'jp', '칸폭', '칸높이', '원문글자수', 'note', 'ko']


def _read(p):
    with open(p, encoding='utf-8-sig', newline='') as f:
        rd = csv.DictReader(f)
        return list(rd.fieldnames or []), list(rd)


def _write(p, cols, rows):
    with open(p, 'w', encoding='utf-8-sig', newline='') as f:
        wr = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore')
        wr.writeheader()
        wr.writerows(rows)


def _grids(d):
    ps = sorted(Path(d).glob('BOXES_*.csv'))
    if not ps:
        raise SystemExit(f'imgreq: {d} 에 BOXES_*.csv 가 없다')
    return ps


def _edit_rows(rows):
    return [r for r in rows if (r.get('kind') or 'edit').strip() != 'keep' and norm_class(r.get('분류') or r.get('class')) != 'keep']


def _jp(r):
    return (r.get('jp') or r.get('ja') or '').strip()


def make(grids, out):
    rows, seen = [], set()
    for p in _grids(grids):
        _, rs = _read(p)
        for r in _edit_rows(rs):
            key = ((r.get('file') or '').strip(), (r.get('id') or '').strip())
            if not key[1]:
                raise SystemExit(f'imgreq: {p.name} 에 id 가 빈 edit 상자가 있다 ({_jp(r)!r}) — id 를 채운다')
            if key in seen:
                raise SystemExit(f'imgreq: {p.name} 에 같은 id 가 둘 — {key}')
            seen.add(key)
            x0, y0, x1, y1 = (int(float(r[k])) for k in ('x0', 'y0', 'x1', 'y1'))
            jp = _jp(r)
            rows.append({'file': key[0], 'id': key[1], '분류': norm_class(r.get('분류') or r.get('class')),
                         'jp': jp, '칸폭': x1 - x0, '칸높이': y1 - y0, '원문글자수': len(jp.replace(' ', '').replace('\\n', '')),
                         'note': r.get('note') or '', 'ko': r.get('ko') or ''})
    _write(out, COLS, rows)
    blank = sum(1 for r in rows if not r['ko'].strip())
    print(f'imgreq: 요청표 {out} — 상자 {len(rows)}개 (ko 빈 것 {blank}개)')
    return 0


def apply(grids, req):
    _, want = _read(req)
    ko = {((r.get('file') or '').strip(), (r.get('id') or '').strip()): (r.get('ko') or '') for r in want}
    used, changed = set(), 0
    for p in _grids(grids):
        cols, rs = _read(p)
        if 'ko' not in cols:
            cols.append('ko')
        hit = False
        for r in rs:
            k = ((r.get('file') or '').strip(), (r.get('id') or '').strip())
            if k in ko:
                used.add(k)
                if (r.get('ko') or '') != ko[k]:
                    r['ko'] = ko[k]
                    changed += 1
                    hit = True
        if hit:
            _write(p, cols, rs)
    miss = [k for k in ko if k not in used]
    print(f'imgreq: 격자 파일에 ko {changed}칸 넣음')
    for k in miss:
        print(f'  맞는 상자 없음: {k[0]} {k[1]}')
    rc = check(grids)
    return 1 if miss else rc


def check(grids):
    blank = []
    for p in _grids(grids):
        _, rs = _read(p)
        blank += [(r.get('file'), r.get('id'), _jp(r), norm_class(r.get('분류') or r.get('class'))) for r in _edit_rows(rs)
                  if not (r.get('ko') or '').strip()]
    if not blank:
        print('imgreq: ko 빈 상자 없음')
        return 0
    print(f'imgreq: ko 빈 상자 {len(blank)}개 (bg 는 Codex 에 맡길 때는 비어도 되지만, 렌더 전에는 채운다)')
    for f, i, jp, c in blank:
        print(f'  {f} {i} [{c}] {jp}')
    return 1


def main(argv=None):
    ap = argparse.ArgumentParser(prog='img.py imgreq', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--grids', required=True, help='격자 파일 폴더 (BOXES_*.csv)')
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--out', help='만들 요청표 CSV')
    g.add_argument('--apply', help='채운 요청표 CSV — ko 를 격자 파일에 넣는다')
    g.add_argument('--check', action='store_true', help='ko 가 빈 edit 상자만 보인다 (있으면 끝 코드 1)')
    a = ap.parse_args(argv)
    if a.out:
        return make(a.grids, a.out)
    if a.apply:
        return apply(a.grids, a.apply)
    return check(a.grids)


if __name__ == '__main__':
    sys.exit(main())
