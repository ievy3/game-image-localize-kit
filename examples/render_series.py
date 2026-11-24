# -*- coding: utf-8 -*-
"""계열 렌더 예시 — 투명 바탕에 흰 명조 한 줄(나레이션 카드 같은 것).

작업 폴더의 render/<계열>.py 로 복사해 고쳐 쓴다. 한 계열 = 같은 모양의 그림 묶음(글꼴·크기·정렬이 같은 것).

    python render/<계열>.py [그림 이름 …]        (이름을 주지 않으면 분류 clear 상자가 있는 그림 전부)

맨 위 설명에 「원문이 어떤가 → 무엇으로 왜」를 적어 둔다(다음 사람이 같은 계열을 이어서 할 수 있게):
  원문: 흰 붓 느낌 명조, 외곽선 없음, 몸통 14~15px, 가운데 정렬.
  글꼴: 원문이 매끈한 글씨 → Noto Serif KR Bold 를 원문 높이로('orig'). 칸을 넘으면 자간 → 장평 → 작은 크기.
        벡터가 그 높이에서 뭉개지면 Galmuri11.
"""
import os
import sys

KIT_TOOLS = os.environ.get('IMGKIT_TOOLS') or r'<키트 폴더>/tools'      # ← 키트 위치로 고친다
sys.path.insert(0, KIT_TOOLS)
from imgrender import init, run_series  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
init(work=os.path.join(HERE, '..'))     # 이 스크립트가 <작업 폴더>/render/ 에 있다고 본다
PACK = ''                               # 원본이 src/<하위 폴더>/ 에 있으면 그 이름 (예 'image')

STYLE = dict(
    _group='all',                        # 한 그림 안의 상자는 같은 크기·자간으로
    spec=('NSB', 'orig'),                # (글꼴 키, 크기) — 'orig' = 원문 글자 높이에 맞춘 크기에서 시작(권장). 숫자도 된다
    pixel=[('G11',)],                    # 원문이 도트 글씨이거나 벡터가 뭉개질 때 쓸 화소 글꼴(제 크기). 없으면 늘 벡터
    # ink='smooth',                      # 원문 판정(도트/매끈)이 틀렸을 때 사람이 정한다 · h=15 원문 높이를 사람이 정할 때
    spacings=[(2, -2), (0, 0), ('tight', 4)],   # (글자 사이, 띄어쓰기 칸 보정) · 'tight' = 닿지 않게 당기기
    align='center',                      # 원본 잉크의 가운데에 맞춘다 (left · center · right)
    color='auto',                        # 원본 잉크 밝기 / 또는 (255, 255, 255)
    mode='alpha',                        # 원본 잉크 재는 법: bright(밝은 몸통) · alpha · loose
    # outline=(1, (0, 0, 0), 1.0),       # 외곽선 (반지름, 색, 알파)
    # shadow=((1, 1), (0, 0, 0), 0.6),   # 그림자
)


if __name__ == '__main__':
    import glob
    from imgrender import GRIDS, edit_boxes
    names = sys.argv[1:] or [os.path.basename(p)[6:-4] for p in sorted(glob.glob(os.path.join(GRIDS, 'BOXES_*.csv')))]
    names = [n for n in names if edit_boxes(n, 'clear')]
    # 계열 전체를 한 번에: 원문 크기가 같은 글씨(같은 _group·같은 상자 id)는 모든 그림에서 같은 글꼴·크기로 (keep 상자는 run 이 늘 지킨다)
    run_series(PACK, names, lambda b: STYLE)
