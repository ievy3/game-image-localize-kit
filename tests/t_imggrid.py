"""2.7.8 단위 시험 — 그림 격자·정본 묶음(imggrid).
    python tests/t_imggrid.py
"""
import csv
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from PIL import Image

KIT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT / 'tools'))
import imggrid  # noqa: E402


def read_rows(p):
    with open(p, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def t_csv_alpha(tmp):
    """상자 CSV(+ja·ko, keep 1행) · 투명 그림 · 512×256 아닌 크기 → 묶음 · zip · 행 수 · 격자 크기 · 투명 칸 합성."""
    src = tmp / 'src'
    src.mkdir()
    im = Image.new('RGBA', (200, 100), (0, 0, 0, 0))
    im.paste((255, 0, 0, 255), (10, 10, 60, 30))
    im.save(src / 'a.png')
    spec = tmp / 'boxes.csv'
    spec.write_text('file,x0,y0,x1,y1,kind,jp,ko,note\n'
                    'a.png,10,10,60,30,,開始,시작,제목\n'
                    'a.png,70,10,120,30,edit,終了,종료,\n'
                    'a.png,0,80,50,100,keep,©SEGA,,\n', encoding='utf-8')
    out = tmp / 'bundle'
    r = subprocess.run([sys.executable, str(KIT / 'tools' / 'img.py'), 'imggrid', '--spec', str(spec), '--src', str(src),
                        '--out', str(out), '--keep', 'START', '--scale', 'auto'], capture_output=True, text=True, encoding='utf-8')
    assert r.returncode == 0, r.stdout + r.stderr
    rows = read_rows(out / '정본.csv')
    assert [(x['no'], x['ja'], x['ko']) for x in rows] == [('1', '開始', '시작'), ('2', '終了', '종료')], rows
    z = imggrid.auto_scale(200, 100)
    assert z == 8, z
    g = Image.open(out / 'grid' / 'a_grid.png')
    assert g.size == (200 * z, 100 * z), g.size
    assert g.getpixel((150 * z + 5, 60 * z + 5)) == imggrid.BG[:3]          # 투명 칸은 어두운 바탕에 합성
    assert Image.open(out / 'orig' / 'a.png').tobytes() == im.tobytes()      # 원본은 그대로
    guide = (out / '지시사항.txt').read_text(encoding='utf-8-sig')
    assert '[반드시 지킬 것]' in guide and '8. 순서' in guide and '200×100 · 투명한 곳 있음' in guide and 'START' in guide
    assert '투명도도 원본 그대로' in guide
    assert '지난번에 틀린 것' not in guide
    names = set(zipfile.ZipFile(out.with_name('bundle.zip')).namelist())
    assert names == {'orig/a.png', 'grid/a_grid.png', '지시사항.txt', '정본.csv', '상자.csv'}, names
    assert 'result/ 에 저장' in guide
    assert [(x['x0'], x['kind']) for x in read_rows(out / '상자.csv')] == [('10', 'edit'), ('70', 'edit'), ('0', 'keep')]


def t_py_spec(tmp):
    """.py 정본(SPEC·BUNDLE_TITLE·MISTAKES) · 512×256 → 3배 · 지난번에 틀린 것 · 상자 밖 좌표는 거부."""
    src = tmp / 'src2'
    src.mkdir()
    Image.new('RGB', (512, 256), (20, 60, 90)).save(src / 'b.png')
    spec = tmp / 'spec.py'
    spec.write_text("BUNDLE_TITLE = '시험 묶음'\nMISTAKES = '- 이름을 바꿈'\n"
                    "SPEC = {'b.png': [((0, 0, 100, 20), 'あ', '아', '본문'), ((100, 20, 200, 40), 'い', '이', '')]}\n",
                    encoding='utf-8')
    s, meta = imggrid.load_spec(spec)
    n, rows, zp = imggrid.build(s, src, tmp / 'b2', meta)
    assert (n, rows) == (1, 2) and zp.is_file()
    assert Image.open(tmp / 'b2' / 'grid' / 'b_grid.png').size == (1536, 768)
    guide = (tmp / 'b2' / '지시사항.txt').read_text(encoding='utf-8-sig')
    assert guide.startswith('시험 묶음') and '- 이름을 바꿈' in guide and '3배로' in guide
    s['b.png'].append(((500, 250, 520, 256), 'う', '우', '', 'edit'))
    try:
        imggrid.build(s, src, tmp / 'b3', meta)
        raise AssertionError('그림 밖 상자를 받아들였다')
    except SystemExit as e:
        assert '그림' in str(e)


def t_erase_only(tmp):
    """--erase-only(bg 요청): ko 가 빈 정본을 받고, 지시문에 「한국어를 그대로 쓴다」 규칙이 없다."""
    src = tmp / 'src3'
    src.mkdir()
    Image.new('RGBA', (64, 32), (90, 30, 30, 255)).save(src / 'c.png')       # 알파 채널만 있고 다 불투명(튜토리얼 같은 그림)
    spec = tmp / 'erase.csv'
    spec.write_text('file,x0,y0,x1,y1,ja,ko\nc.png,2,2,40,20,タイトル,\n', encoding='utf-8')
    try:
        imggrid.load_spec(spec)
        raise AssertionError('ko 가 빈 정본을 기본 방식에서 받아들였다')
    except SystemExit:
        pass
    assert imggrid.main(['--spec', str(spec), '--src', str(src), '--out', str(tmp / 'e1'), '--erase-only']) == 0
    guide = (tmp / 'e1' / '지시사항.txt').read_text(encoding='utf-8-sig')
    assert '불투명 그림' in guide and '투명도도 원본 그대로' not in guide          # 다 불투명한 그림에 「투명도 유지」를 적지 않는다
    assert imggrid.ERASE_MARK in guide and '지운 배경만' in guide and '한국어를 글자 하나 바꾸지 말고' not in guide and '지우기만' in guide, guide[:400]


def main():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        for t in (t_csv_alpha, t_py_spec, t_erase_only):
            t(tmp)
            print('ok', t.__name__)
    print('imggrid 시험 통과')


if __name__ == '__main__':
    main()
