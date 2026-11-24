"""그림 글자 칸 검사 — 레이아웃 파일의 UV 칸과 대조해 새 글자가 칸 경계를 넘는지 본다.

    img.py imgcells --layout 레이아웃파일 --orig 원본.png --result 결과.png
    img.py imgcells --pairs 목록.csv        (열 layout, orig, result — 여러 장)

게임은 한 그림(아틀라스)을 칸으로 잘라 쓴다. 글자가 칸을 넘으면 옆 칸에 조각이 보이고(「!」),
이 칸에서는 잘린다. 칸은 추측하지 말고 읽는다(34.Shining Blade: 「노래」가 15px 칸에 걸림, 2026-10-30).

칸 찾기: 레이아웃 파일 안의 4바이트 float 넷(u0 v0 u1 v1)이 0~1 이고, 그림 크기를 곱하면 정수가 되는 곳.
형식을 몰라도 찾히지만 우연히 맞는 값도 섞이므로, 원본 잉크가 경계를 넘지 않고 안에 잉크가 있는 칸만 진짜로 본다.
다른 게임의 레이아웃이 float UV 가 아니면 칸이 0개로 나온다 — 그때는 「칸 없음」으로 알리고 통과로 치지 않는다.
종료 코드: 0 걸침 없음, 1 걸침 있음, 2 칸을 못 찾음.
"""
import _utf8  # noqa: F401  (출력 UTF-8)
import argparse
import csv
import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ALPHA = 0x20


def find_rects(data, W, H, min_w=8, min_h=6):
    """레이아웃 바이트에서 그림 크기에 맞는 UV 사각형(x0, y0, x1, y1)."""
    n = len(data) // 4
    vals = struct.unpack(f'<{n}f', data[:n * 4])
    rects = set()
    for i in range(n - 3):
        u0, v0, u1, v1 = vals[i:i + 4]
        if 0 <= u0 < u1 <= 1 and 0 <= v0 < v1 <= 1:
            q = (u0 * W, v0 * H, u1 * W, v1 * H)
            if all(abs(x - round(x)) < .01 for x in q) and q[2] - q[0] >= min_w and q[3] - q[1] >= min_h:
                rects.add(tuple(round(x) for x in q))
    return rects


def crosses(M, r):
    """칸 경계 안쪽·바깥쪽 줄에 잉크가 맞닿은 칸 수(0 = 경계를 넘는 획 없음)."""
    x0, y0, x1, y1 = r
    H, W = M.shape
    c = 0
    if x0 > 0:
        c += int((M[y0:y1, x0 - 1] & M[y0:y1, x0]).sum())
    if x1 < W:
        c += int((M[y0:y1, x1 - 1] & M[y0:y1, x1]).sum())
    if y0 > 0:
        c += int((M[y0 - 1, x0:x1] & M[y0, x0:x1]).sum())
    if y1 < H:
        c += int((M[y1 - 1, x0:x1] & M[y1, x0:x1]).sum())
    return c


def check(layout, orig, result):
    """(진짜로 본 칸 수, 걸린 칸 목록, 칸 밖 새 잉크 칸 수)."""
    A = np.array(Image.open(orig).convert('RGBA'))[..., 3] > ALPHA
    K = np.array(Image.open(result).convert('RGBA'))[..., 3] > ALPHA
    if A.shape != K.shape:
        raise SystemExit(f'{result}: 크기가 원본과 다르다 {K.shape} != {A.shape}')
    H, W = A.shape
    real, bad = 0, []
    cover = np.zeros(A.shape, bool)
    for r in sorted(find_rects(Path(layout).read_bytes(), W, H)):
        x0, y0, x1, y1 = r
        if not A[y0:y1, x0:x1].any() or crosses(A, r) or (x1 - x0) * (y1 - y0) > W * H * .6:
            continue
        real += 1
        cover[y0:y1, x0:x1] = True
        if crosses(K, r):
            bad.append(r)
    outside = int((K & ~A & ~cover).sum()) if real else 0
    return real, bad, outside


def main(argv=None):
    ap = argparse.ArgumentParser(prog='img.py imgcells', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--layout'); ap.add_argument('--orig'); ap.add_argument('--result')
    ap.add_argument('--pairs', help='열 layout, orig, result 인 CSV')
    a = ap.parse_args(argv)
    if a.pairs:
        with open(a.pairs, encoding='utf-8-sig', newline='') as f:
            jobs = [(r['layout'], r['orig'], r['result']) for r in csv.DictReader(f)]
    elif a.layout and a.orig and a.result:
        jobs = [(a.layout, a.orig, a.result)]
    else:
        ap.error('--layout --orig --result 또는 --pairs')
    flagged, nocell = 0, 0
    for layout, orig, result in jobs:
        real, bad, outside = check(layout, orig, result)
        if not real:
            nocell += 1
            print(f'칸 없음 {Path(result).name}: {Path(layout).name} 에서 칸을 못 찾음 — 이 그림은 검사되지 않았다')
        elif bad:
            flagged += 1
            print(f'걸림 {Path(result).name}: 칸 {real}개 중 {bad[:8]} · 칸 밖 새 잉크 {outside}')
    print(f'그림 {len(jobs)}장 · 걸림 {flagged} · 칸 없음 {nocell} (가짜 칸이 섞일 수 있다 — 걸린 칸은 원본과 나란히 보고 판단)')
    return 1 if flagged else (2 if nocell else 0)


if __name__ == '__main__':
    sys.exit(main())
