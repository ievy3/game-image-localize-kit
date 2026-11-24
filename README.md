# 그림 글자 한글화 키트 — Codex CLI · Claude Code

한국어 | [English](README.en.md)

게임 그림(PNG) 속 **일본어 글자를 한글로 바꾸는** 키트다. 기종은 가리지 않는다 — PSP·3DS·NDS·GBA 무엇이든, 그림을 PNG 로 꺼내고 다시 넣는 일은 그 기종의 도구가 하고, 이 키트는 **원본 PNG 를 받아 고친 PNG 를 내놓는 데까지**를 맡는다.

- 그림마다 글자 자리를 **격자 파일**로 재고, 글자 상자를 **투명 글씨 · 배경 글씨 · 디자인 글씨** 세 갈래로 나눠 처리한다.
- 배경이 있는 글자는 **Codex CLI** 에 격자·지시문 꾸러미로 맡기고(1차 수정 → 2차 점검), 결과를 기계로 검사한다.
- 사람은 **비교 HTML**(원본 | 결과 | 바뀐 화소)로 보고 통과/불통을 고른다.
- 계정은 이 PC 에서 그 CLI 에 로그인한 사람의 것을 쓴다. 키트에는 계정·키가 없다.
- 키트 폴더 이름·위치, 작업 폴더 이름·위치는 마음대로 정한다.

규칙 전체는 [`IMAGE_RULES.md`](IMAGE_RULES.md), 글꼴은 [`FONTS.md`](FONTS.md).

## 세 갈래 — 글자 뒤에 무엇이 있나, 어떤 서체인가
| 갈래 | 어떤 글자 | 지우기 | 한글 쓰기 |
|---|---|---|---|
| **투명 글씨** (`clear`) | 글자 둘레가 투명해 지우면 빈자리만 남는 글씨 | 직접 (글자 자리 알파 0) | **직접 렌더** (글꼴) |
| **배경 글씨** (`bg`) | 뒤에 그림·무늬가 있지만 보통 글꼴로 다시 쓸 수 있는 글씨 | **Codex** — 일본어를 지우고 그 자리 배경을 살린다, 남은 찌꺼기를 기계로 잰다 | **직접 렌더** (일본어를 지운 자리에) |
| **디자인 글씨** (`design`) | 로고·손글씨·장식 서체·효과 글씨 | **Codex** | **Codex** (완성 그림까지) |

배경 글씨와 디자인 글씨 사이가 애매하면 디자인 글씨. 격자 파일의 「분류」 열에 `clear` / `bg` / `design` / `keep`(그대로 둘 글자)을 적는다. 「직접」은 작업하는 사람이나 에이전트(Claude Code 등)가 글꼴로 그린다는 뜻이다 — 같은 화면의 메뉴처럼 글꼴·크기·정렬(±2px)을 맞춰야 하는 글자는 이 편이 정확하다.

## 처음 한 번 (PC 마다)
1. **파이썬 3.9 이상**, 꾸러미: `pip install pillow numpy scipy opencv-python-headless`
2. **Codex CLI** (배경 글씨·디자인 글씨에 필요): Node.js 설치 후 `npm install -g @openai/codex` → `codex login` 으로 본인 계정(ChatGPT 요금제 또는 OpenAI API) 로그인.
   - 확인: `python tools/img.py login`
   - 기본 모델 `gpt-6.2-astra` · 추론 high. 요금제에 없으면 `imgcodex --model <이름>`.
3. 글꼴: OFL 글꼴이면 무엇이든 라이선스 파일과 함께 `fonts/` 에 둔다 (추천 목록 [`FONTS.md`](FONTS.md)).
4. (선택) **Claude Code** — 아래 스킬 `/image-localize` 로 대화하며 진행하려면.

## 작업 폴더 (기본)
게임마다 아무 곳에 하나 만든다. 이름은 자유.
```
<작업 폴더>/
  src/      게임에서 꺼낸 원본 PNG
  grids/    격자 파일 BOXES_<그림 이름>.csv
  bundles/  Codex 꾸러미 (imggrid → imgcodex)
  ko/       판정을 통과한 최종 PNG — 이것만 게임에 넣는다
  review/   비교 HTML, 판정 CSV
```

## 순서
명령은 모두 `python <키트>/tools/img.py <명령>` (명령마다 `-h`). 아래는 작업 폴더에서 부른다고 보고 `img.py` 로 줄인다.

1. **글씨 있는 그림 찾기** — 흰 바탕만 보지 말고 어두운 바탕 대조표도 본다.
   `img.py imgdark --src src --out dark`
2. **격자 파일** — 그림마다 `grids/BOXES_<이름>.csv`.
   열 `file,x0,y0,x1,y1,kind,id,jp,ko,분류,grid,note` (x1·y1 은 상자 밖, `kind` = edit/keep, `분류` = clear/bg/design/keep). 원본을 직접 보고 8px 격자 칸에 맞춰 잰다. 분류표는 사용자가 승인한다.
3. **번역문** — 상자마다 넣을 한국어(`ko`)를 정한다. 먼저 사용자가 고른다: (가) 번역본(요청본)을 준다 / (나) 에이전트가 번역하고 사용자가 승인한다.
   `img.py imgreq --grids grids --out 번역요청.csv` → 요청표(`file, id, 분류, jp, 칸폭, 칸높이, 원문글자수, note, ko`)의 `ko` 를 채운다 → `img.py imgreq --grids grids --apply 번역요청.csv` 로 격자 파일에 넣는다 (`--check` = 빈 칸 보기). `ko` 가 빈 투명·디자인 글씨는 렌더·꾸러미가 멈춘다.
4. **투명 글씨** — 렌더 함수 모음 `tools/imgrender.py` 로 그린다. `examples/render_series.py` 를 `render/<계열>.py` 로 복사해 글꼴·크기·정렬만 고치고 `python render/<계열>.py`.
   상자 안 일본어를 지우고(넘친 외곽선까지) → 원본 잉크 위치에 맞춰 한글을 그리고 → 칸을 넘으면 작은 크기·좁은 자간으로 → `ko/` 에 저장한다. Claude·Codex·사람 누구나 같은 함수로 한다.
   글꼴은 **원문 충실** — 원문이 도트 글씨면 화소 글꼴, 매끈한 글씨면 벡터 글꼴을 **원문 글자 높이**로(`spec=('키', 'orig')`). 매끈한데 그 높이의 벡터가 뭉개지면 그때만 화소 글꼴(STYLE 의 `pixel=`). 판정·높이는 `imgrender` 가 재서 상자마다 출력한다. 계열은 `run_series` 로 — 원문 크기가 같은 글씨는 모든 그림에서 같은 글꼴·크기.
5. **배경 글씨** — 일본어를 지우고 그 자리 배경을 살리는 일을 Codex 에:
   `img.py imggrid --spec grids --class bg --src src --out bundles/bg_01`
   `img.py imgcodex bundles/bg_01` → `bundles/bg_01/result/`, `codex_check.csv` (찌꺼기 덩어리 12화소 넘으면 불통)
   → 통과한 배경 위에 한글을 렌더한다 (계열 스크립트에서 `run(..., cls='bg', start='bundles/bg_01/result')`).
6. **디자인 글씨** — 한글까지 넣은 완성 그림을 Codex 에:
   `img.py imggrid --spec grids --class design --src src --out bundles/design_01`
   `img.py imgcodex bundles/design_01`
7. **판정** — 고치거나 받을 때마다 비교 HTML 을 만들어 본다:
   `img.py imgview --orig src --result <결과 폴더> --boxes grids --title "<계열·회차>" --out review/<제목>.html`
   통과/불통·메모 → 「판정 CSV 내려받기」 → `review/` 에 둔다. 통과한 것만 `ko/` 로.
8. (게임 레이아웃이 있으면) **칸 검사**: `img.py imgcells --layout <레이아웃> --orig <원본> --result <결과>`

`imgcodex` 가 두 번(1차·2차 + 고치기) 하고도 불통인 그림은 그 꾸러미(`bundles/<이름>.zip` — 격자 그림·지시사항.txt·정본 포함)를 사람이 직접 고치거나 다른 도구에 맡긴다.

## 도구
| 명령 | 하는 일 |
|---|---|
| `imgreq` | 번역 요청표 — 격자 파일의 일본어를 표로 뽑기(`--out`) · 채운 한국어를 격자 파일에 넣기(`--apply`) · `ko` 빈 상자 보기(`--check`) |
| `imggrid` | 정본(격자 파일) + 원본 → 격자 그림(번호 상자) · `지시사항.txt` · `정본.csv` · `상자.csv` 꾸러미 + .zip. `--class clear|bg|design` 로 갈래 고르기 (`bg` 면 일본어를 지우고 배경을 살리기만 맡기는 꾸러미), `--mistakes` = 지난번에 틀린 것 |
| `imgcodex` | 꾸러미를 Codex 에: 1차 「지시사항대로」 → 같은 세션 2차 점검 → 기계 검사(결과 있음·같은 크기·투명도·회색 상자 그대로·배경 글씨 찌꺼기) → 불통이면 같은 세션에 한 번 더. 그래도 불통이면 끝 코드 2. `--check-only` 는 Codex 없이 검사만 |
| `imgview` | 원본(상자 겹침) · 결과 · 바뀐 화소를 나란히 보는 HTML — 통과/불통·메모, 판정 CSV |
| `imgdark` | 어두운 바탕 대조표 — 흰 글자 · 투명 바탕 그림을 놓치지 않게 |
| `imgcells` | 게임 레이아웃의 UV 칸(0~1 float)과 대조해 새 글자가 칸을 넘는지 |
| `imgbox` | 상자 밖 · 화면 밖 · 그대로 둘 상자의 바뀐 화소 지도 (참고용 — 합격 조건 아님) |
| `login` | Codex CLI 설치 · 로그인 여부 |

## 스킬 `/image-localize` — Claude Code · Codex
키트에 스킬 `.claude/skills/image-localize/` 가 들어 있다. 부르면 위 순서를 대화로 진행한다 — 격자 파일 초안, 갈래 나누기(승인은 사람), 번역문(요청본 또는 에이전트 번역 — 먼저 묻는다), 투명·배경 글씨 한글 렌더, Codex 꾸러미 만들기·맡기기, 비교 HTML.
- **Claude Code**: 키트 폴더에서 `claude` 를 열면 설치 없이 잡힌다 → `/image-localize`.
- **어느 폴더에서나 / Codex 에서도**: `python install_skill.py` — `%USERPROFILE%\.claude\skills\` 와 `%USERPROFILE%\.codex\skills\` 에 복사한다 (`--claude`·`--codex` 로 한쪽만, `--remove` 로 지우기). 새로 연 세션부터 잡힌다. Codex 에서는 「그림 한글화 하자」처럼 말하면 된다.
- 어느 쪽에서 부르든 배경 글씨·디자인 글씨는 `imgcodex` 가 **Codex CLI 를 따로 띄워** 처리한다. 그래서 Codex CLI 설치·로그인은 늘 필요하다. `imgcodex` 는 부르기 전에 로그인을 확인하고, 안 되어 있으면 `codex login` 을 안내하고 끝 코드 3 으로 멈춘다.

## 시험
`python tests/t_imggrid.py` · `t_imgreq.py` · `t_imgcodex.py`(가짜 Codex) · `t_imgview.py` · `t_imgcells.py` — 모두 「통과」가 나와야 한다.

## 만든 사람·라이선스
- 만든 사람: **NP (Noctil Patchworks)** — https://ievy3.github.io/
- MIT (`LICENSE`). 글꼴·Codex CLI·파이썬 꾸러미는 들어 있지 않다 — 각자의 라이선스·약관을 따른다.

## 알아 둘 것
- 지시문·검사 문구는 **일본어 → 한국어** 기준이다. 다른 원문 언어에 쓰려면 `tools/imggrid.py` 의 지시문을 고친다.
- 배경 글씨 찌꺼기 기준 12화소는 표본 5장으로 정한 잠정값이다. 상자 안에 무늬·테두리가 있으면 깨끗해도 불통으로 갈 수 있다(안전한 쪽).
- Codex 결과의 품질은 모델·요금제에 따라 다르다. 통과한 결과도 사람이 비교 HTML 로 본다.
