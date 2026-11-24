"""단위 시험 — imgcodex(꾸러미 → 코덱스 1차·2차·고치기 → 기계 검사). 진짜 코덱스 대신 가짜 명령을 쓴다.
    python tests/t_imgcodex.py
"""
import csv
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

KIT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT / 'tools'))
import imggrid  # noqa: E402
import imgcodex  # noqa: E402

BGC = (30, 60, 90, 255)

# 가짜 코덱스: 받은 인자·프롬프트를 calls.txt 에 적고, 1차·2차는 원본을 그대로 result/ 에(글자가 남음), 「기계 검사」 프롬프트에만 상자를 바탕색으로 채운다.
FAKE = r'''
import json, shutil, sys
from pathlib import Path
from PIL import Image, ImageDraw
args = sys.argv[1:]
prompt = sys.stdin.buffer.read().decode('utf-8')
here = Path.cwd()
with open(here / 'calls.txt', 'a', encoding='utf-8') as f:
    f.write(json.dumps({'args': args, 'prompt': prompt}, ensure_ascii=False) + '\n')
assert args[-1] == '-' and '-m' in args
print(json.dumps({'type': 'thread.started', 'thread_id': args[args.index('resume') + 1] if 'resume' in args else 'T-1'}))
res = here / 'result'
for o in (here / 'orig').glob('*.png'):
    im = Image.open(o).convert('RGBA')
    if '기계 검사' in prompt:
        ImageDraw.Draw(im).rectangle((10, 10, 39, 29), fill=(30, 60, 90, 255))
    if not (res / o.name).exists() or '기계 검사' in prompt:
        im.save(res / o.name)
Path(args[args.index('-o') + 1]).write_text('done', encoding='utf-8')
'''


def bundle(tmp, erase):
    src = tmp / ('src_e' if erase else 'src_b')
    src.mkdir()
    im = Image.new('RGBA', (64, 40), BGC)
    im.paste((255, 255, 255, 255), (14, 14, 34, 24))            # 「글자」
    im.paste((200, 30, 30, 255), (50, 0, 64, 10))               # 그대로 둘 곳
    im.save(src / 'a.png')
    spec = tmp / ('e.csv' if erase else 'b.csv')
    spec.write_text('file,x0,y0,x1,y1,kind,ja,ko\na.png,10,10,40,30,,決定,결정\na.png,50,0,64,10,keep,○,\n', encoding='utf-8')
    out = tmp / ('be' if erase else 'bb')
    s, meta = imggrid.load_spec(spec, erase)
    imggrid.build(s, src, out, meta, erase_only=erase)
    return out


def calls(b):
    import json
    return [json.loads(x) for x in (b / 'calls.txt').read_text(encoding='utf-8').splitlines()]


def t_erase_retry(tmp):
    """bg: 1차·2차는 찌꺼기가 남아 불통 → 같은 세션(resume T-1)에 고치기 → 통과. 모델·추론·stdin 프롬프트."""
    b = bundle(tmp, True)
    fake = tmp / 'fake_codex.py'
    fake.write_text(FAKE, encoding='utf-8')
    assert imgcodex.main([str(b), '--codex', str(fake)]) == 0
    cs = calls(b)
    assert len(cs) == 3, len(cs)
    assert '지시사항.txt' in cs[0]['prompt'] and 'resume' not in cs[0]['args'] and 'workspace-write' in cs[0]['args']
    assert '폰트 크기·굵기·줄 간격' in cs[1]['prompt'] and cs[1]['args'][:3] == ['exec', 'resume', 'T-1']
    assert '기계 검사' in cs[2]['prompt'] and '찌꺼기' in cs[2]['prompt'] and 'resume' in cs[2]['args']
    for c in cs:
        a = c['args']
        assert a[a.index('-m') + 1] == 'gpt-6.2-astra' and 'model_reasoning_effort="high"' in a
    rows = list(csv.DictReader(open(b / 'codex_check.csv', encoding='utf-8-sig')))
    assert rows[0]['verdict'] == '통과' and rows[0]['keep_changed'] == '0', rows


def t_erase_fail(tmp):
    """--retries 0: 고치기를 보내지 않고 불통 → 끝 코드 2."""
    (tmp / 'x').mkdir()
    b = bundle(tmp / 'x', True)
    assert imgcodex.main([str(b), '--codex', str(tmp / 'fake_codex.py'), '--retries', '0']) == 2
    assert len(calls(b)) == 2
    assert '찌꺼기' in list(csv.DictReader(open(b / 'codex_check.csv', encoding='utf-8-sig')))[0]['why']


def t_check_only(tmp):
    """design --check-only: 결과 없음 · 크기 다름 · 회색 상자 바뀜 · 투명한 원본을 RGB 로 받음은 불통. 다 불투명한 원본은 RGB 로 와도, 상자 안만 바뀌면 통과."""
    b = bundle(tmp, False)
    assert not imgcodex.is_erase(b)
    assert imgcodex.main([str(b), '--check-only']) == 2                         # 결과 없음
    o = Image.open(b / 'orig' / 'a.png')
    r = b / 'result' / 'a.png'
    cases = [(o.resize((32, 20)), '크기')]
    k = o.copy()
    k.paste((0, 0, 0, 255), (55, 2, 60, 6))
    cases.append((k, '회색 상자'))
    for im, word in cases:
        im.save(r)
        rows, _ = imgcodex.check(b)
        assert rows[0]['verdict'] == '불통' and word in rows[0]['why'], (word, rows)
    t = o.copy()                                                                 # 원본에 정말 투명한 화소가 있으면 RGB 결과는 불통
    t.putpixel((0, 39), (0, 0, 0, 0))
    t.save(b / 'orig' / 'a.png')
    t.convert('RGB').save(r)
    rows, _ = imgcodex.check(b)
    assert rows[0]['verdict'] == '불통' and '투명도' in rows[0]['why'], rows
    o.save(b / 'orig' / 'a.png')
    ok = o.copy()
    ok.paste((90, 90, 90, 255), (12, 12, 38, 28))
    ok.convert('RGB').save(r)                                                    # 원본은 알파 채널만 있고 다 불투명 → RGB 로 와도 통과
    assert imgcodex.check(b)[0][0]['verdict'] == '통과'
    ok.save(r)
    assert imgcodex.main([str(b), '--check-only']) == 0


def t_cli(tmp):
    r = subprocess.run([sys.executable, str(KIT / 'tools' / 'img.py'), 'imgcodex', '-h'], capture_output=True, text=True, encoding='utf-8')
    assert r.returncode == 0 and '2차' in r.stdout, r.stdout + r.stderr


def main():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        for t in (t_erase_retry, t_erase_fail, t_check_only, t_cli):
            t(tmp)
            print('ok', t.__name__)
    print('imgcodex 시험 통과')


if __name__ == '__main__':
    main()
