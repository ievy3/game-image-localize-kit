"""2.9.0 단위 시험 — 그림 칸 검사(imgcells)·어두운 대조표(imgdark).
    python tests/t_imgcells.py
"""
import struct
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

KIT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT / 'tools'))
import imgcells  # noqa: E402
import imgdark  # noqa: E402


def png(path, boxes, size=(128, 32)):
    a = np.zeros((size[1], size[0], 4), np.uint8)
    a[..., :3] = 255
    for x0, y0, x1, y1 in boxes:
        a[y0:y1, x0:x1, 3] = 255
    Image.fromarray(a, 'RGBA').save(path)


def layout(path, rects, size=(128, 32)):
    W, H = size
    b = b''.join(struct.pack('<4f', x0 / W, y0 / H, x1 / W, y1 / H) for x0, y0, x1, y1 in rects)
    path.write_bytes(b'\0' * 16 + b)


def main():
    with tempfile.TemporaryDirectory() as td:
        t = Path(td)
        layout(t / 'L.bin', [(0, 0, 26, 15), (26, 0, 104, 15), (105, 1, 120, 15)])
        png(t / 'orig.png', [(2, 2, 24, 12), (30, 2, 100, 12), (107, 3, 118, 13)])
        # 칸 안 글자 → 걸림 없음
        png(t / 'ok.png', [(2, 2, 24, 12), (30, 2, 90, 12), (107, 3, 118, 13)])
        real, bad, _ = imgcells.check(t / 'L.bin', t / 'orig.png', t / 'ok.png')
        assert real == 3 and not bad, (real, bad)
        assert imgcells.main(['--layout', str(t / 'L.bin'), '--orig', str(t / 'orig.png'), '--result', str(t / 'ok.png')]) == 0
        # 「노래」처럼 두 칸에 걸치면 걸림
        png(t / 'bad.png', [(2, 2, 24, 12), (30, 2, 90, 12), (101, 3, 123, 13)])
        real, bad, _ = imgcells.check(t / 'L.bin', t / 'orig.png', t / 'bad.png')
        assert (105, 1, 120, 15) in bad, bad
        assert imgcells.main(['--layout', str(t / 'L.bin'), '--orig', str(t / 'orig.png'), '--result', str(t / 'bad.png')]) == 1
        # 칸을 못 찾으면 통과로 치지 않는다
        (t / 'none.bin').write_bytes(b'\xff' * 64)
        assert imgcells.main(['--layout', str(t / 'none.bin'), '--orig', str(t / 'orig.png'), '--result', str(t / 'ok.png')]) == 2
        # 어두운 대조표: 흰 글자·투명 그림은 나오고, 불투명·빈 그림은 빠진다
        src = t / 'src'
        src.mkdir()
        png(src / 'white_text.png', [(2, 2, 60, 12)])
        Image.new('RGBA', (64, 64), (0, 0, 0, 255)).save(src / 'opaque.png')
        Image.new('RGBA', (64, 64), (0, 0, 0, 0)).save(src / 'empty.png')
        names = [n for n, _ in imgdark.pick(src, set())]
        assert names == ['white_text.png'], names
        assert imgdark.main(['--src', str(src), '--out', str(t / 'out')]) == 0
        assert (t / 'out' / 'dark_00.png').exists()
    print('t_imgcells PASS')


if __name__ == '__main__':
    main()
