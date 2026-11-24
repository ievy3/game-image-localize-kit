r"""스킬 /image-localize 를 이 PC 의 사용자 폴더에 설치한다 — 어느 폴더에서든 부를 수 있게.

    python install_skill.py              Claude Code 와 Codex 둘 다 (있는 쪽만)
    python install_skill.py --claude     %USERPROFILE%\.claude\skills\image-localize\
    python install_skill.py --codex      %USERPROFILE%\.codex\skills\image-localize\
    python install_skill.py --remove     둘 다에서 지운다

키트 폴더 안에서 Claude Code 를 열면 설치하지 않아도 .claude/skills 가 바로 잡힌다.
스킬은 키트 위치를 모른다 — 처음 부를 때 키트 폴더를 묻는다(또는 지금 폴더에서 찾는다).
"""
import argparse
import shutil
import sys
from pathlib import Path

NAME = 'image-localize'
SRC = Path(__file__).resolve().parent / '.claude' / 'skills' / NAME
HOME = Path.home()
TARGETS = {'claude': HOME / '.claude' / 'skills' / NAME, 'codex': HOME / '.codex' / 'skills' / NAME}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--claude', action='store_true')
    ap.add_argument('--codex', action='store_true')
    ap.add_argument('--remove', action='store_true')
    a = ap.parse_args()
    which = [k for k in TARGETS if getattr(a, k)] or list(TARGETS)
    for k in which:
        dst = TARGETS[k]
        if a.remove:
            if dst.exists():
                shutil.rmtree(dst)
                print(f'지움: {dst}')
            continue
        if not dst.parent.parent.exists() and not (a.claude or a.codex):
            print(f'건너뜀: {k} — {dst.parent.parent} 가 없다 (설치 안 됨)')
            continue
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(SRC, dst)
        print(f'설치: {dst}  ({"Claude Code: /image-localize" if k == "claude" else "Codex: 「그림 한글화」처럼 말하면 잡힌다"})')
    print('새로 연 세션부터 잡힌다.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
