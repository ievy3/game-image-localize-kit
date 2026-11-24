"""결과 화면 열기 — 만든 HTML 을 사용자의 기본 브라우저로 띄운다.

    import showhtml; showhtml.open_html(path, no_open=a.no_open)

KIT_NO_OPEN=1(자체 시험·배치)이거나 --no-open 이면 띄우지 않고 경로만 찍는다.
브라우저를 「띄우기」만 한다 — 창에 키·마우스를 보내지 않는다.
"""
import os
import sys
import webbrowser
from pathlib import Path


def open_html(path, no_open=False):
    p = Path(path).resolve()
    if no_open or os.environ.get('KIT_NO_OPEN'):
        print(f'  결과 화면: {p} (띄우지 않음)')
        return False
    try:
        if sys.platform == 'win32':
            os.startfile(str(p))          # noqa: S606 — 기본 브라우저
        else:
            webbrowser.open(p.as_uri())
        print(f'  결과 화면을 브라우저로 띄웠다: {p}')
        return True
    except OSError as e:
        print(f'  결과 화면: {p} (띄우지 못함: {e})')
        return False
