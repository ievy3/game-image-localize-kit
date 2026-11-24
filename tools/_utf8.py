"""출력을 UTF-8 로 — 파이프·다른 프로그램으로 받을 때 Windows 기본(cp949)에서 「—」 같은 글자로 멈추지 않게."""
import sys

for _st in (sys.stdout, sys.stderr):
    try:
        if _st and (getattr(_st, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
            _st.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError, OSError):
        pass
