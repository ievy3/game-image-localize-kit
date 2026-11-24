"""그림 비교 화면 — 고친 그림을 사용자가 브라우저로 보고 판정하는 HTML 한 장(그림 내장, 인터넷 필요 없음).

    img.py imgview --orig src --result ko [--boxes grids] [--title "메뉴 계열 표본"]
                   [--files a.png,b.png] [--out review/<이름>.html] [--per-page 60] [--no-open]

한 그림마다: 원본(격자 상자 겹쳐 보기) | 결과 | 바뀐 화소(빨강 = 상자 밖, 노랑 = 상자 안) 를 같은 배율로 나란히,
    상자별 일본어 → 한국어 · 분류, 칸 밖 변경 표시(참고 — 일본어를 지운 자리면 괜찮다), 통과/불통 단추와 메모.
화면 위: 배율 맞춤(세 칸을 화면 폭에)·1·2·3·4배(화소 그대로), 바탕 체크무늬·어둡게·밝게, 걸러 보기(전체·미정·통과·불통·칸 밖 변경).
판정은 브라우저에 남고, 「판정 CSV 내려받기」로 file,verdict,memo 를 받는다 — 받은 파일을 review/ 에 두면 작업하는 에이전트가 읽는다.
--boxes 는 상자 CSV 하나 또는 폴더(안의 *.csv 를 모두 읽는다, 열 file,x0,y0,x1,y1[,kind,id,jp,ko,분류]).
그림이 --per-page 보다 많으면 여러 쪽(<이름>_p01.html …)으로 나누고 쪽끼리 잇는다.
만든 뒤 첫 쪽을 기본 브라우저로 띄운다(--no-open 또는 KIT_NO_OPEN=1 이면 경로만 — showhtml.py).
"""
import _utf8  # noqa: F401  (출력 UTF-8)
import argparse
import base64
import csv
import html
import io
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

import imgbox
import showhtml

IMG_EXT = imgbox.IMG_EXT


def _box_rows(path):
    """상자 CSV(또는 폴더) → {파일 이름: [행 dict]}."""
    out = {}
    if not path:
        return out
    p = Path(path)
    files = sorted(p.glob('*.csv')) if p.is_dir() else [p]
    for f in files:
        with open(f, encoding='utf-8-sig', newline='') as fh:
            for r in csv.DictReader(fh):
                key = (r.get('file') or '').replace('\\', '/').strip()
                if not key or not all((r.get(k) or '').strip() for k in ('x0', 'y0', 'x1', 'y1')):
                    continue
                out.setdefault(key, []).append(r)
    return out


def _lookup(table, rel):
    return table.get(rel) or table.get(Path(rel).name) or []


def _png(im):
    b = io.BytesIO()
    im.save(b, 'PNG', optimize=True)
    return 'data:image/png;base64,' + base64.b64encode(b.getvalue()).decode()


def _diff(orig, result, rows):
    """바뀐 화소 그림: 원본을 옅은 회색으로, 바뀐 화소는 상자 안 노랑 · 상자 밖 빨강. → (그림, 안, 밖)"""
    a, b = np.asarray(orig.convert('RGBA')).astype(int), np.asarray(result.convert('RGBA')).astype(int)
    changed = np.any(a != b, axis=2)
    inside = np.zeros(changed.shape, bool)
    for r in rows:
        if (r.get('kind') or 'edit').strip().lower() == 'edit':
            x0, y0, x1, y1 = (int(float(r[k])) for k in ('x0', 'y0', 'x1', 'y1'))
            inside[max(0, y0):max(0, y1), max(0, x0):max(0, x1)] = True
    grey = (a[..., :3].mean(axis=2) * 0.25 + 150).astype(np.uint8)
    out = np.stack([grey, grey, grey, np.full_like(grey, 255)], axis=2)
    out[changed & inside] = (255, 200, 0, 255)
    out[changed & ~inside] = (230, 30, 30, 255)
    return Image.fromarray(out, 'RGBA'), int((changed & inside).sum()), int((changed & ~inside).sum())


def _card(i, rel, orig_p, res_p, rows):
    io_, ir = Image.open(orig_p), Image.open(res_p)
    w, h = io_.size
    note = []
    if ir.size != io_.size:
        note.append(f'크기 다름: 원본 {w}x{h} · 결과 {ir.width}x{ir.height}')
        diff_uri, n_in, n_out = '', 0, 0
    else:
        d, n_in, n_out = _diff(io_, ir, rows)
        diff_uri = _png(d)
    chk = imgbox.check_pair(orig_p, res_p, [((int(float(r['x0'])), int(float(r['y0'])), int(float(r['x1'])), int(float(r['y1']))),
                                             (r.get('kind') or 'edit').strip().lower()) for r in rows]) if rows and ir.size == io_.size else None
    verdict = chk['verdict'] if chk else ('FAIL' if note else '상자 없음')
    if chk and chk.get('note'):
        note.append(chk['note'])
    rects = ''.join(
        f'<rect x="{int(float(r["x0"]))}" y="{int(float(r["y0"]))}" width="{int(float(r["x1"])) - int(float(r["x0"]))}" '
        f'height="{int(float(r["y1"])) - int(float(r["y0"]))}" class="{"keep" if (r.get("kind") or "").strip().lower() == "keep" else "edit"}"/>'
        for r in rows)
    texts = ''.join(
        f'<tr><td>{html.escape(r.get("id") or "")}</td><td>{html.escape(r.get("분류") or r.get("kind") or "")}</td>'
        f'<td lang="ja">{html.escape(r.get("jp") or r.get("ja") or "")}</td><td>{html.escape(r.get("ko") or "")}</td></tr>'
        for r in rows if (r.get('jp') or r.get('ja') or r.get('ko')))
    kinds = sorted({(r.get('분류') or '').strip() for r in rows} - {'', 'keep'})
    tags = ''.join(f'<span class="tag">{html.escape(k)}</span>' for k in kinds)
    badge = {'PASS': 'ok'}.get(verdict, 'warn')
    label = {'PASS': '칸 밖 변경 없음', 'FAIL': '칸 밖 변경 있음 — 일본어 지운 자리인지 보기'}.get(verdict, verdict)
    svg = f'<svg viewBox="0 0 {w} {h}" class="ov" preserveAspectRatio="none">{rects}</svg>' if rects else ''
    diff_fig = (f'<figure><figcaption>바뀐 화소 <small>안 {n_in} · <b class="{"warn-t" if n_out else ""}">밖 {n_out}</b></small></figcaption>'
                f'<div class="pic" style="--w:{w};--h:{h}"><img src="{diff_uri}" alt=""></div></figure>') if diff_uri else ''
    return f'''<article class="card" data-file="{html.escape(rel)}" data-check="{verdict}">
<header><span class="no">{i}</span><h2>{html.escape(rel)}</h2>{tags}<span class="badge {badge}">{html.escape(label)}</span><span class="size">{w}×{h}</span></header>
<div class="row">
<figure><figcaption>원본 <label><input type="checkbox" class="showbox" checked> 상자</label></figcaption><div class="pic" style="--w:{w};--h:{h}"><img src="{_png(io_)}" alt="">{svg}</div></figure>
<figure><figcaption>결과</figcaption><div class="pic" style="--w:{w};--h:{h}"><img src="{_png(ir)}" alt=""></div></figure>
{diff_fig}
</div>
{f'<table class="tx"><thead><tr><th>상자</th><th>분류</th><th>일본어</th><th>한국어</th></tr></thead><tbody>{texts}</tbody></table>' if texts else ''}
{''.join(f'<p class="note">{html.escape(n)}</p>' for n in note)}
<footer><button class="v pass" data-v="통과">통과</button><button class="v fail" data-v="불통">불통</button><input class="memo" placeholder="메모 — 불통이면 무엇이 문제인지"></footer>
</article>'''


CSS = '''
:root{--bg:#f6f7f9;--card:#fff;--ink:#1d2330;--sub:#667085;--line:#e3e6ec;--ok:#1f9d55;--bad:#d64545;--warn:#c98a00;--accent:#3b6fd8}
@media (prefers-color-scheme:dark){:root{--bg:#14171c;--card:#1d2128;--ink:#e6e8ec;--sub:#9aa3b2;--line:#2c323c;--accent:#7aa2ff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 "Pretendard","Malgun Gothic",system-ui,sans-serif}
.top{position:sticky;top:0;z-index:5;background:var(--card);border-bottom:1px solid var(--line);padding:10px 16px;display:flex;flex-wrap:wrap;gap:10px 18px;align-items:center}
.top h1{font-size:16px;margin:0 8px 0 0}.top .grp{display:flex;gap:4px;align-items:center;color:var(--sub)}
.top button,.card button{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:6px;padding:3px 10px;cursor:pointer;font:inherit}
.top button.on{background:var(--accent);border-color:var(--accent);color:#fff}
.count{color:var(--sub)}.pages a{margin:0 3px;color:var(--accent)}
main{padding:16px;display:grid;gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.card.vpass{border-left:5px solid var(--ok)}.card.vfail{border-left:5px solid var(--bad)}
.card header{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:8px}
.card h2{font-size:14px;margin:0;word-break:break-all}.no{color:var(--sub)}.size{color:var(--sub);margin-left:auto}
.tag{background:var(--line);border-radius:4px;padding:0 6px;font-size:12px}
.badge{border-radius:4px;padding:0 6px;font-size:12px;color:#fff}.badge.ok{background:var(--ok)}.badge.bad{background:var(--bad)}.badge.warn{background:var(--warn)}
.warn-t{color:var(--warn)}
.row{display:flex;flex-wrap:wrap;gap:12px;align-items:flex-start;overflow-x:auto}
figure{margin:0}figcaption{font-size:12px;color:var(--sub);margin-bottom:3px;display:flex;gap:8px}
.pic{position:relative;width:calc(var(--w)*var(--z)*1px);height:calc(var(--h)*var(--z)*1px);background:var(--pbg);background-size:16px 16px;outline:1px solid var(--line)}
.pic img,.pic svg{position:absolute;inset:0;width:100%;height:100%;image-rendering:pixelated}
.ov rect{fill:none;stroke-width:1;vector-effect:non-scaling-stroke}.ov .edit{stroke:#ff2a2a}.ov .keep{stroke:#999;stroke-dasharray:3 2}
.nobox .ov{display:none}
.tx{border-collapse:collapse;margin-top:8px;font-size:13px}.tx td,.tx th{border:1px solid var(--line);padding:2px 8px;text-align:left}
.note{color:var(--warn);margin:6px 0 0}
.card footer{display:flex;gap:6px;margin-top:10px;align-items:center}
.card .v.on.pass{background:var(--ok);border-color:var(--ok);color:#fff}.card .v.on.fail{background:var(--bad);border-color:var(--bad);color:#fff}
.memo{flex:1;min-width:120px;border:1px solid var(--line);border-radius:6px;padding:4px 8px;background:var(--bg);color:var(--ink);font:inherit}
body.fit .row{flex-wrap:nowrap}body.fit figure{flex:1 1 0;min-width:0}
body.fit .pic{width:100%;height:auto;aspect-ratio:var(--w)/var(--h);max-width:calc(var(--w)*4px)}
@media (max-width:700px){.size{margin-left:0}body.fit .row{flex-wrap:wrap}body.fit figure{flex:1 1 100%}}
'''

JS = r'''
const KEY='imgview:'+document.title;let st={};try{st=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){}
const save=()=>{try{localStorage.setItem(KEY,JSON.stringify(st))}catch(e){}};
const BG={chk:'repeating-conic-gradient(#bbb 0 25%,#eee 0 50%)',dark:'#202024',light:'#ffffff'};
function setZ(z){document.body.classList.toggle('fit',z=='fit');if(z!='fit')document.documentElement.style.setProperty('--z',z);document.querySelectorAll('[data-z]').forEach(b=>b.classList.toggle('on',b.dataset.z==z));try{localStorage.setItem('imgview:z',z)}catch(e){}}
function setB(k){document.documentElement.style.setProperty('--pbg',BG[k]);document.querySelectorAll('[data-b]').forEach(b=>b.classList.toggle('on',b.dataset.b==k));try{localStorage.setItem('imgview:b',k)}catch(e){}}
function paint(c){const s=st[c.dataset.file]||{};c.classList.toggle('vpass',s.v=='통과');c.classList.toggle('vfail',s.v=='불통');
 c.querySelectorAll('.v').forEach(b=>b.classList.toggle('on',b.dataset.v==s.v));c.querySelector('.memo').value=s.m||''}
function count(){const cs=[...document.querySelectorAll('.card')];const n=v=>cs.filter(c=>(st[c.dataset.file]||{}).v==v).length;
 document.getElementById('cnt').textContent=`${cs.length}장 · 통과 ${n('통과')} · 불통 ${n('불통')} · 미정 ${cs.length-n('통과')-n('불통')}`}
function filt(f){document.querySelectorAll('[data-f]').forEach(b=>b.classList.toggle('on',b.dataset.f==f));
 document.querySelectorAll('.card').forEach(c=>{const v=(st[c.dataset.file]||{}).v;
  c.style.display=(f=='all'||(f=='none'&&!v)||f==v||(f=='FAIL'&&c.dataset.check!='PASS'))?'':'none'})}
document.querySelectorAll('.card').forEach(c=>{paint(c);
 c.querySelectorAll('.v').forEach(b=>b.onclick=()=>{const s=st[c.dataset.file]||(st[c.dataset.file]={});s.v=s.v==b.dataset.v?'':b.dataset.v;save();paint(c);count()});
 c.querySelector('.memo').oninput=e=>{(st[c.dataset.file]||(st[c.dataset.file]={})).m=e.target.value;save()};
 c.querySelector('.showbox')?.addEventListener('change',e=>c.classList.toggle('nobox',!e.target.checked))});
document.querySelectorAll('[data-z]').forEach(b=>b.onclick=()=>setZ(b.dataset.z));
document.querySelectorAll('[data-b]').forEach(b=>b.onclick=()=>setB(b.dataset.b));
document.querySelectorAll('[data-f]').forEach(b=>b.onclick=()=>filt(b.dataset.f));
document.getElementById('csv').onclick=()=>{const q=s=>'"'+String(s||'').replace(/"/g,'""')+'"';
 const rows=[...document.querySelectorAll('.card')].map(c=>{const s=st[c.dataset.file]||{};return [q(c.dataset.file),q(s.v),q(s.m)].join(',')});
 const blob=new Blob(['﻿file,verdict,memo\n'+rows.join('\n')+'\n'],{type:'text/csv'});const a=document.createElement('a');
 a.href=URL.createObjectURL(blob);a.download=document.title.replace(/[\\/:*?"<>| ]+/g,'_')+'_판정.csv';a.click()};
let z0='fit',b0='chk';try{z0=localStorage.getItem('imgview:z')||z0;b0=localStorage.getItem('imgview:b')||b0}catch(e){}
setZ(z0);setB(b0);filt('all');count();
'''


def _page(title, cards, pages, k, check_filter='칸 밖 변경'):
    nav = '' if len(pages) < 2 else '<span class="grp pages">쪽 ' + ''.join(
        f'<a href="{html.escape(p)}">{"<b>" + str(j + 1) + "</b>" if j == k else j + 1}</a>' for j, p in enumerate(pages)) + '</span>'
    t = title if len(pages) < 2 else f'{title} ({k + 1}/{len(pages)})'
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(t)}</title><style>{CSS}</style></head><body>
<div class="top"><h1>{html.escape(t)}</h1><span class="count" id="cnt"></span>
<span class="grp">배율 <button data-z="fit">맞춤</button><button data-z="1">1×</button><button data-z="2">2×</button><button data-z="3">3×</button><button data-z="4">4×</button></span>
<span class="grp">바탕 <button data-b="chk">체크</button><button data-b="dark">어둡게</button><button data-b="light">밝게</button></span>
<span class="grp">보기 <button data-f="all">전체</button><button data-f="none">미정</button><button data-f="통과">통과</button><button data-f="불통">불통</button>{f'<button data-f="FAIL">{html.escape(check_filter)}</button>' if check_filter else ''}</span>
<button id="csv">판정 CSV 내려받기</button>{nav}</div>
<main>{"".join(cards)}</main><script>{JS}</script></body></html>'''


def main(argv=None):
    ap = argparse.ArgumentParser(prog='imgview', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--orig', required=True, help='원본 PNG 폴더(또는 파일)')
    ap.add_argument('--result', required=True, help='결과 PNG 폴더(또는 파일)')
    ap.add_argument('--boxes', help='상자 CSV 또는 그 폴더(grids)')
    ap.add_argument('--files', help='이 이름만(쉼표로)')
    ap.add_argument('--title', default='그림 비교')
    ap.add_argument('--out', help='HTML 경로 (기본 review/<제목>.html)')
    ap.add_argument('--per-page', type=int, default=60)
    ap.add_argument('--no-open', action='store_true', help='브라우저로 띄우지 않는다(경로만)')
    a = ap.parse_args(argv)
    orig, result = Path(a.orig), Path(a.result)
    if result.is_file():
        pairs = [(orig if orig.is_file() else orig / result.name, result, result.name)]
    else:
        pairs = [(orig / p.relative_to(result), p, p.relative_to(result).as_posix())
                 for p in sorted(result.rglob('*')) if p.suffix.lower() in IMG_EXT]
    if a.files:
        want = {s.strip() for s in a.files.split(',') if s.strip()}
        pairs = [x for x in pairs if x[2] in want or Path(x[2]).name in want]
    missing = [rel for o, _, rel in pairs if not o.is_file()]
    pairs = [x for x in pairs if x[0].is_file()]
    if not pairs:
        raise SystemExit('imgview: 원본과 짝이 맞는 결과 그림이 없다' + (f' (원본 없음: {", ".join(missing[:5])})' if missing else ''))
    boxes = _box_rows(a.boxes)
    safe = ''.join(ch if ch.isalnum() or ch in '-_.' else '_' for ch in a.title).strip('_') or 'img_review'
    out = Path(a.out) if a.out else Path('review') / f'{safe}.html'
    out.parent.mkdir(parents=True, exist_ok=True)
    n = max(1, a.per_page)
    chunks = [pairs[i:i + n] for i in range(0, len(pairs), n)]
    names = [out.name] if len(chunks) == 1 else [f'{out.stem}_p{j + 1:02d}{out.suffix}' for j in range(len(chunks))]
    fails = 0
    for k, chunk in enumerate(chunks):
        cards = []
        for i, (o, r, rel) in enumerate(chunk, k * n + 1):
            c = _card(i, rel, o, r, _lookup(boxes, rel))
            fails += 'data-check="PASS"' not in c
            cards.append(c)
        (out.parent / names[k]).write_text(_page(a.title, cards, names, k), encoding='utf-8')
    total = sum((out.parent / x).stat().st_size for x in names) / 1e6
    print(f'imgview: {len(pairs)}장, 칸 밖 변경(참고) {fails}장 → {", ".join(str(out.parent / x) for x in names)} ({total:.1f} MB)')
    if missing:
        print(f'  원본이 없어 뺀 결과 {len(missing)}장: {", ".join(missing[:10])}')
    print('  사용자에게 이 경로도 알린다. 판정은 화면의 「판정 CSV 내려받기」로 돌아온다.')
    showhtml.open_html(out.parent / names[0], a.no_open)
    return 0


if __name__ == '__main__':
    sys.exit(main())
