"""번역 요청표(imgreq) 시험 — 요청표 만들기 · 채워 넣기 · 빈 칸 보기 · 렌더의 빈 ko 막음.
    python tests/t_imgreq.py
"""
import csv
import subprocess
import sys
import tempfile
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent


def run(*a):
    return subprocess.run([sys.executable, str(KIT / 'tools' / 'img.py'), 'imgreq', *a], capture_output=True, text=True, encoding='utf-8')


def rows(p):
    with open(p, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def main():
    with tempfile.TemporaryDirectory() as d:
        t = Path(d)
        g = t / 'grids'
        g.mkdir()
        (g / 'BOXES_a.csv').write_text('file,x0,y0,x1,y1,kind,id,jp,ko,분류,grid,note\n'
                                       'a.png,0,0,64,16,edit,b1,開始,,clear,,메뉴\n'
                                       'a.png,0,16,64,32,edit,b2,終了,종료,bg,,\n'
                                       'a.png,0,32,64,48,keep,k1,©SEGA,,keep,,\n', encoding='utf-8-sig')
        req = t / '번역요청.csv'
        r = run('--grids', str(g), '--out', str(req))
        assert r.returncode == 0, r.stdout + r.stderr
        rq = rows(req)
        assert [(x['id'], x['jp'], x['칸폭'], x['원문글자수'], x['ko']) for x in rq] == [('b1', '開始', '64', '2', ''), ('b2', '終了', '64', '2', '종료')], rq
        r = run('--grids', str(g), '--check')
        assert r.returncode == 1 and 'b1' in r.stdout, r.stdout
        rq[0]['ko'] = '시작'
        with open(req, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(rq[0]))
            w.writeheader()
            w.writerows(rq)
        r = run('--grids', str(g), '--apply', str(req))
        assert r.returncode == 0 and '1칸' in r.stdout, r.stdout + r.stderr
        gr = rows(g / 'BOXES_a.csv')
        assert [x['ko'] for x in gr] == ['시작', '종료', ''] and list(gr[0]) [-1] == 'note', gr
        # 맞는 상자가 없는 행은 끝 코드 1
        with open(req, 'a', encoding='utf-8-sig', newline='') as f:
            f.write('a.png,b9,clear,何,8,8,1,,뭐\n')
        r = run('--grids', str(g), '--apply', str(req))
        assert r.returncode == 1 and 'b9' in r.stdout, r.stdout
        # 렌더: ko 빈 상자가 있으면 멈춘다
        (g / 'BOXES_a.csv').write_text('file,x0,y0,x1,y1,kind,id,jp,ko,분류,grid,note\na.png,0,0,64,16,edit,b1,開始,,clear,,\n', encoding='utf-8-sig')
        code = ('import sys; sys.path.insert(0, r"%s"); import imgrender; imgrender.GRIDS = r"%s"; '
                'imgrender.run(None, "a", lambda b: {})') % (KIT / 'tools', g)
        r = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, encoding='utf-8')
        assert r.returncode != 0 and 'ko 가 비었다' in (r.stdout + r.stderr), r.stdout + r.stderr
    print('imgreq 시험 통과')


if __name__ == '__main__':
    main()
