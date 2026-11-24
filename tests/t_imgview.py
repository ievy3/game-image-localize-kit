"""imgview 시험 — 작은 그림 두 쌍으로 비교 HTML 을 만들고, 그림 내장·상자·검사 결과·쪽 나누기를 본다.
    python tests/t_imgview.py
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

KIT = Path(__file__).resolve().parent.parent


def main():
    with tempfile.TemporaryDirectory() as td:
        t = Path(td)
        (t / 'src').mkdir(); (t / 'ko').mkdir()
        for n in ('a.png', 'b.png'):
            Image.new('RGBA', (16, 8), (0, 0, 0, 0)).save(t / 'src' / n)
        Image.new('RGBA', (16, 8), (0, 0, 0, 0)).save(t / 'ko' / 'a.png')
        im = Image.new('RGBA', (16, 8), (0, 0, 0, 0)); im.putpixel((15, 7), (255, 0, 0, 255)); im.save(t / 'ko' / 'b.png')
        (t / 'grid.csv').write_text('file,x0,y0,x1,y1,kind,id,jp,ko,분류\na.png,0,0,8,8,edit,t1,テスト,시험,clear\nb.png,0,0,8,8,edit,t1,テスト,시험,clear\n', encoding='utf-8')
        cmd = [sys.executable, str(KIT / 'tools' / 'imgview.py'), '--orig', str(t / 'src'), '--result', str(t / 'ko'),
               '--boxes', str(t / 'grid.csv'), '--title', '시험', '--out', str(t / 'out' / 'v.html')]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        assert r.returncode == 0, r.stderr
        h = (t / 'out' / 'v.html').read_text(encoding='utf-8')
        assert h.count('class="card"') == 2 and 'data:image/png;base64,' in h and '시험' in h and 'テスト' in h
        assert 'data-check="PASS"' in h and 'data-check="FAIL"' in h, '상자 밖 변경을 FAIL 로 못 잡음'
        assert '판정 CSV 내려받기' in h and 'http' not in h.split('<script>')[0].split('</title>')[1], '외부 자원'
        r = subprocess.run(cmd[:-2] + ['--out', str(t / 'pg' / 'v.html'), '--per-page', '1'], capture_output=True, text=True, encoding='utf-8', errors='replace')
        assert r.returncode == 0 and (t / 'pg' / 'v_p01.html').is_file() and (t / 'pg' / 'v_p02.html').is_file(), r.stdout + r.stderr
    print('imgview 시험 통과')


if __name__ == '__main__':
    main()
