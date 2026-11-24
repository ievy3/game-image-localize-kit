"""imgcodex — imggrid 꾸러미를 코덱스 CLI 에 맡기고(1차 지시사항대로 → 2차 점검), 결과를 기계로 검사한다.

    python tools/img.py imgcodex bundles/<꾸러미> [--model gpt-6.2-astra] [--effort high] [--retries 1]
                                      [--residue 12] [--thr 24] [--timeout 1800] [--check-only] [--codex 명령]

과정 (사용자가 코덱스에 하던 그대로, 사용자 결정 2026-11-17):
  1차  같은 세션: 「이 폴더의 지시사항.txt 를 읽고 지시사항대로 수행」 → 결과는 <꾸러미>/result/
  2차  같은 세션 이어서: 「한글 폰트 크기·굵기·줄 간격이 다른 곳, 일본어 흔적, 찌꺼기, 번역을 넣으며 잘린 기존 문구」 점검·수정
       (한 번 더 거치면 더 나아진다 — 44 GLAP 시험에서 1차에 남은 알파 잔상을 2차가 지웠다)
  검사 그림마다: 결과 있음 · 같은 크기 · 원본에 투명도가 있으면 결과에도 · 회색 상자(keep) 변경 0 → 아니면 「불통」
       배경 글씨(bg) 꾸러미(--erase-only)는 imgresidue 의 찌꺼기 재기 — 덩어리가 --residue 를 넘으면 「불통」
       상자 밖 변경 수는 참고로만 적는다(넘친 획을 지운 자리일 수 있다 — imgbox 와 같은 규칙)
  다시  불통이 있으면 같은 세션에 「기계 검사에서 걸린 것」을 보내 고치게 한다(--retries 번). 그래도 불통이면 끝 코드 2 → 사용자에게. Codex 에 로그인되어 있지 않으면 부르기 전에 끝 코드 3.
  디자인 글씨(design)의 한글 문구·모양은 기계로 가리지 않는다 — 통과한 결과도 판정하는 사람·모델이 imgview 로 본다.

남는 것: <꾸러미>/result/ · <꾸러미>/_codex/(단계별 jsonl·마지막 말) · <꾸러미>/codex_check.csv
모델: 기본 gpt-6.2-astra · 추론 high. 프로젝트 .codex/config.toml 은 믿지 않은 폴더에서 무시되므로 늘 -m 으로 준다((Web) 모델 금지).
--check-only: 코덱스를 부르지 않고 result/ 만 검사한다. --codex: 코덱스 명령(시험용 .py 도 받는다, 환경 변수 KIT_CODEX).
"""
import _utf8  # noqa: F401  (출력 UTF-8)
import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import imggrid  # noqa: E402

try:
    import imgresidue                     # 배경 글씨 찌꺼기 재기 (numpy·opencv). opencv 가 없으면 건너뛰고 알린다
    import cv2  # noqa: F401
except ImportError:
    imgresidue = None

OUTSIDE_FAILS = False                     # 상자 밖 변경: 이 키트는 참고만(사용자 결정 2026-11-10). 「상자 밖 0」 키트는 True
MODEL = 'gpt-6.2-astra'
EFFORT = 'high'
RESULT = imggrid.RESULT_DIR

PASS1 = (f'이 폴더의 지시사항.txt 를 읽고 지시사항대로 수행해라. 결과 PNG 는 {RESULT}/ 폴더에 orig/ 의 원본과 같은 이름으로 저장해라. '
         '질문하지 말고 끝까지 수행해라.')
PASS2 = (f'{RESULT}/ 의 결과물을 다시 점검해라. 완성본에서 한글 폰트 크기·굵기·줄 간격이 다른 곳이나 일본어 흔적이 남은 곳은 수정해줘. '
         '일어 잔존이나 찌꺼기, 번역을 넣으면서 기존 문구가 잘린 것도 확인해줘. '
         f'고친 결과는 {RESULT}/ 에 같은 이름으로 덮어써라. 질문하지 말고 끝까지 수행해라.')
FIX = ('키트의 기계 검사에서 아래가 걸렸다. 지시사항.txt 를 다시 지키면서 고쳐 {result}/ 에 같은 이름으로 덮어써라. '
       '질문하지 말고 끝까지 수행해라.\n{items}')
COLS = ['file', 'verdict', 'why', 'size', 'outside_changed', 'keep_changed', 'residue_max', 'residue_boxes']


def codex_cmd(arg):
    c = arg or os.environ.get('KIT_CODEX')
    if c and c.lower().endswith('.py'):
        return [sys.executable, c]
    exe = shutil.which(c or 'codex')
    if not exe:
        raise SystemExit('imgcodex: codex CLI 를 찾지 못했다 (npm i -g @openai/codex 또는 --codex)')
    return [exe]


def login_state(cmd):
    """(ok, 한 줄). Codex 에 로그인되어 있는지만 본다 — 계정 이름·이메일은 돌려주지 않는다."""
    try:
        r = subprocess.run(cmd + ['login', 'status'], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, f'Codex 로그인 상태를 못 읽었다: {e}'
    out = (r.stdout or '') + (r.stderr or '')
    if r.returncode == 0 and 'not logged in' not in out.lower():
        how = 'ChatGPT' if 'ChatGPT' in out else ('API 키' if 'API' in out else '')
        return True, f"Codex 로그인됨{(' (' + how + ')') if how else ''}"
    return False, ('Codex 에 로그인되어 있지 않다 — 명령 프롬프트에서 `codex login` 으로 본인 계정'
                   '(ChatGPT 요금제 또는 OpenAI API)으로 로그인한 뒤 다시')


def run_codex(cmd, bundle, step, prompt, model, effort, thread=None, timeout=1800):
    """한 단계 → thread_id. 프롬프트는 stdin 으로(따옴표·한글이 셸을 거치지 않는다)."""
    log = bundle / '_codex'
    log.mkdir(exist_ok=True)
    last = log / f'{step}_last.txt'
    common = ['-m', model, '-c', f'model_reasoning_effort="{effort}"', '--skip-git-repo-check', '--json', '-o', str(last)]
    if thread:
        args = cmd + ['exec', 'resume', thread] + common + ['-']
    else:
        args = cmd + ['exec'] + common + ['-s', 'workspace-write', '-C', str(bundle), '-']
    print(f'imgcodex: {step} — 코덱스({model} {effort}) 실행 중 …', flush=True)
    r = subprocess.run(args, input=prompt.encode('utf-8'), cwd=bundle, capture_output=True, timeout=timeout)
    (log / f'{step}.jsonl').write_bytes(r.stdout)
    (log / f'{step}.err').write_bytes(r.stderr)
    tid = thread
    for line in r.stdout.decode('utf-8', 'replace').splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get('type') == 'thread.started':
            tid = ev.get('thread_id') or tid
    if r.returncode != 0 or not tid:
        tail = r.stderr.decode('utf-8', 'replace').strip().splitlines()[-3:]
        raise SystemExit(f'imgcodex: {step} 실패(끝 코드 {r.returncode}) — {log / (step + ".err")}\n  ' + '\n  '.join(tail))
    if last.is_file():
        print('  코덱스: ' + last.read_text(encoding='utf-8', errors='replace').strip().replace('\n', ' ')[:300])
    return tid


def read_boxes(bundle):
    """{그림: [((x0,y0,x1,y1), 'edit'|'keep')]} — 상자.csv(imggrid 꾸러미), 없으면 정본.csv(번호 상자만)."""
    p = bundle / '상자.csv'
    if not p.is_file():
        p = bundle / '정본.csv'
    out = {}
    with open(p, encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            b = tuple(int(float(r[k])) for k in ('x0', 'y0', 'x1', 'y1'))
            out.setdefault(r['file'], []).append((b, (r.get('kind') or 'edit').strip() or 'edit'))
    return out


def is_erase(bundle):
    g = (bundle / '지시사항.txt').read_text(encoding='utf-8-sig')
    mark = getattr(imggrid, 'ERASE_MARK', None)
    return bool(mark and mark in g) or '→ 지우기만' in g or '(지우기만)' in g or '(글자만 지움)' in g


def _alpha(im):
    return imggrid._has_alpha(im)


_really_transparent = imggrid.really_transparent   # 채널만 있고 다 불투명하면 RGB 로 와도 괜찮다


def check(bundle, residue_limit=12, thr=24):
    """그림마다 dict(COLS). 배경 글씨(bg) 꾸러미면 찌꺼기도 잰다."""
    if is_erase(bundle) and imgresidue is None:
        print('imgcodex: [경고] opencv 가 없어 찌꺼기를 재지 못한다 — pip install opencv-python-headless (지금은 크기·투명도·회색 상자만 본다)')
    import imgbox
    erase = is_erase(bundle)
    boxes = read_boxes(bundle)
    res_dir = bundle / RESULT
    rows = []
    origs = sorted(p for p in (bundle / 'orig').rglob('*') if p.is_file())
    for o in origs:
        rel = o.relative_to(bundle / 'orig').as_posix()
        r = dict(file=rel, verdict='통과', why='', size='', outside_changed='', keep_changed='', residue_max='', residue_boxes='')
        res = res_dir / rel
        if not res.is_file():
            r.update(verdict='불통', why=f'{RESULT}/{rel} 없음')
            rows.append(r)
            continue
        bx = boxes.get(rel) or boxes.get(Path(rel).name) or []
        io, ir = Image.open(o), Image.open(res)
        r['size'] = f'{io.width}x{io.height}'
        why = []
        if io.size != ir.size:
            why.append(f'크기 다름(결과 {ir.width}x{ir.height})')
        else:
            if _really_transparent(io) and not _alpha(ir):
                why.append('원본의 투명도가 결과에 없음')
            c = imgbox.check_pair(o, res, bx)
            r['outside_changed'], r['keep_changed'] = c.get('outside', 0), c.get('keep', 0)
            if c.get('keep'):
                why.append(f'회색 상자(그대로 둘 곳) {c["keep"]}화소 바뀜')
            if OUTSIDE_FAILS and c.get('outside'):
                why.append(f'상자 밖 {c["outside"]}화소 바뀜({c.get("outside_bbox", "")})')
            if erase and imgresidue:
                a = np.asarray(io.convert('RGBA'))
                b = np.asarray(ir.convert('RGBA'))
                rs = imgresidue.residue(a, b, bx, thr, residue_limit)
                bad = [(x[0], x[3]) for x in rs if x[4] != '통과']
                r['residue_max'] = max([x[3] for x in rs], default=0)
                r['residue_boxes'] = ' '.join(f'{b0}:{big}' for b0, big in bad)
                if bad:
                    why.append('일본어 찌꺼기가 남은 상자 ' + ', '.join(f'({b0[0]},{b0[1]})-({b0[2]},{b0[3]}) 덩어리 {big}화소' for b0, big in bad))
        if why:
            r.update(verdict='불통', why='; '.join(why))
        rows.append(r)
    return rows, erase


def write(bundle, rows):
    with open(bundle / 'codex_check.csv', 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, COLS)
        w.writeheader()
        w.writerows(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(prog='imgcodex', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('bundle', help='img.py imggrid 로 만든 꾸러미 폴더')
    ap.add_argument('--model', default=MODEL)
    ap.add_argument('--effort', default=EFFORT)
    ap.add_argument('--retries', type=int, default=1, help='기계 검사 불통일 때 같은 세션에 고치라고 다시 보내는 횟수 (기본 1)')
    ap.add_argument('--residue', type=int, default=12, help='배경 글씨 찌꺼기 덩어리 기준 화소 (imgresidue)')
    ap.add_argument('--thr', type=int, default=24)
    ap.add_argument('--timeout', type=int, default=1800, help='단계마다 기다리는 초')
    ap.add_argument('--check-only', action='store_true', help='코덱스를 부르지 않고 result/ 만 검사')
    ap.add_argument('--codex', help='코덱스 명령 (기본 PATH 의 codex, 환경 변수 KIT_CODEX)')
    a = ap.parse_args(argv)
    bundle = Path(a.bundle).resolve()
    if not (bundle / '지시사항.txt').is_file() or not (bundle / 'orig').is_dir():
        raise SystemExit(f'imgcodex: {bundle} 는 imggrid 꾸러미가 아니다(지시사항.txt·orig/ 없음)')
    (bundle / RESULT).mkdir(exist_ok=True)
    if not a.check_only:
        cmd = codex_cmd(a.codex)
        if cmd[0] != sys.executable:                 # 시험용 가짜 코덱스(.py)는 로그인 확인을 건너뛴다
            ok, msg = login_state(cmd)
            print(f'imgcodex: {msg}')
            if not ok:
                return 3
        tid = run_codex(cmd, bundle, 'pass1', PASS1, a.model, a.effort, timeout=a.timeout)
        (bundle / '_codex' / 'thread.txt').write_text(tid + '\n', encoding='utf-8')
        run_codex(cmd, bundle, 'pass2', PASS2, a.model, a.effort, tid, a.timeout)
    rows, erase = check(bundle, a.residue, a.thr)
    if not a.check_only:
        for i in range(a.retries):
            bad = [r for r in rows if r['verdict'] != '통과']
            if not bad:
                break
            items = '\n'.join(f'- {r["file"]}: {r["why"]}' for r in bad)
            run_codex(cmd, bundle, f'fix{i + 1}', FIX.format(result=RESULT, items=items), a.model, a.effort, tid, a.timeout)
            rows, erase = check(bundle, a.residue, a.thr)
    write(bundle, rows)
    bad = [r for r in rows if r['verdict'] != '통과']
    kind = '배경 글씨 — 지우기만' if erase else '디자인 글씨 — 완성 그림'
    print(f'imgcodex: {kind} 그림 {len(rows)}장 — 통과 {len(rows) - len(bad)} · 불통 {len(bad)} ({bundle / "codex_check.csv"})')
    for r in bad:
        print(f'  불통 {r["file"]}: {r["why"]}')
    if not erase:
        print('  디자인 글씨의 한글 문구·모양은 기계로 가리지 않는다 — 사람이 img.py imgview 로 본다')
    if bad:
        print('  → 불통 그림은 사용자에게(꾸러미 그대로 넘기거나 --mistakes 로 다시 묶어서)')
    return 2 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
