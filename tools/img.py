"""그림 글자 한글화 키트 — 명령 하나로 도구를 부른다.

    python tools/img.py <명령> [인자 …]      (명령마다 -h)

    imgreq    번역 요청표 — 격자 파일의 일본어를 표로 뽑기(--out) · 채운 한국어를 격자 파일에 넣기(--apply) · 빈 칸 보기(--check)
    imggrid   정본(csv·py) + 원본 → 격자 그림 · 지시사항.txt · 정본.csv · 상자.csv 꾸러미 + .zip
    imgcodex  그 꾸러미를 Codex CLI 에 맡김(1차 지시사항대로 → 2차 점검) + 기계 검사. 불통이 남으면 끝 코드 2
    imgview   원본 · 결과 · 바뀐 화소를 나란히 보는 비교 HTML (통과/불통 판정 → CSV)
    imgdark   어두운 바탕 대조표 — 흰 글자 · 투명 바탕 그림을 「글자 없음」으로 놓치지 않게
    imgcells  게임 레이아웃의 UV 칸과 대조해 새 글자가 칸 경계를 넘는지
    imgbox    상자 밖 · 화면 밖 · 그대로 둘 상자에서 바뀐 화소 지도 (참고용 — 합격 조건 아님)
    login     Codex CLI 설치 · 로그인 여부 (계정 정보는 보이지 않는다)

규칙은 IMAGE_RULES.md, 글꼴은 FONTS.md, 쓰는 순서는 README.md.
"""
import _utf8  # noqa: F401  (출력 UTF-8)
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

CMDS = ("imgreq", "imggrid", "imgcodex", "imgview", "imgdark", "imgcells", "imgbox")


def login():
    import imgcodex
    try:
        cmd = imgcodex.codex_cmd(None)
    except SystemExit:
        print("[--] Codex CLI 가 없다 — Node.js 를 설치하고 `npm install -g @openai/codex` (imgcodex 만 필요, 다른 명령은 없어도 된다)")
        return 1
    ok, msg = imgcodex.login_state(cmd)
    print(("[OK] " if ok else "[--] ") + msg)
    return 0 if ok else 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == "login":
        return login()
    if cmd not in CMDS:
        print(f"모르는 명령: {cmd}\n{__doc__}")
        return 2
    mod = __import__(cmd)
    return mod.main(rest) or 0


if __name__ == "__main__":
    sys.exit(main())
