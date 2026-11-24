# 한글 글꼴

키트에는 글꼴 파일이 들어 있지 않다. **SIL Open Font License(OFL) 글꼴이면 무엇이든** 키트의 `fonts/<글꼴 이름>/` 에 라이선스 파일(OFL.txt 등)과 함께 넣어 쓴다 (다른 곳에 두려면 환경 변수 `IMGKIT_FONTS` 에 그 폴더). 아래는 이 PC 의 한글화 프로젝트들에서 써 본 글꼴 목록이다.

- OFL 이 아닌 글꼴은 게임 그림에 넣어 배포해도 되는 라이선스인지 먼저 확인한다. 윈도우·맥에 딸린 글꼴(바탕·굴림·맑은 고딕 등)은 게임 그림에 넣어 배포할 수 없다.
- 쓴 글꼴의 라이선스 파일(OFL.txt)은 한글 패치 배포 꾸러미에 같이 넣는다.
- 키트 규칙 (`IMAGE_RULES.md` §3): **원문 충실** — 원문이 도트 글씨면 화소 글꼴, 매끈한 글씨면 벡터 글꼴을 원문 높이로. 매끈한 글씨인데 벡터가 그 높이에서 뭉개지면 그때만 화소 글꼴. 한 줄·한 묶음에 한 글꼴, 같은 계열에서 원문 크기가 같은 글씨는 같은 글꼴·크기.
- `imggrid` 는 격자 그림의 번호를 `fonts/Pretendard/Pretendard-Bold.otf` 로 그린다. 없으면 기본 글꼴로 그린다 (그래도 된다).

| 쓰임 | 글꼴 | 받는 곳 |
|---|---|---|
| 본문 (대사·메뉴) | Pretendard | https://github.com/orioncactus/pretendard |
| 본문 | Noto Sans KR | https://fonts.google.com/noto/specimen/Noto+Sans+KR |
| 둥근 고딕 (메뉴·말풍선·안내문) | 나눔스퀘어라운드 (NanumSquareRound) | https://hangeul.naver.com/fonts/search?f=nanum |
| 명조 (분위기 있는 글) | Noto Serif KR | https://fonts.google.com/noto/specimen/Noto+Serif+KR |
| 명조 | 나눔명조 (Nanum Myeongjo) | https://fonts.google.com/specimen/Nanum+Myeongjo |
| 도트 글씨 · 벡터가 뭉개질 때 — 화소 글꼴 | Galmuri (7·9·11 …) | https://github.com/quiple/galmuri |
| 도트 글씨 · 벡터가 뭉개질 때 — 화소 글꼴 | Neo둥근모 (NeoDunggeunmo) | https://github.com/neodgm/neodgm |
| 도트 글씨 · 벡터가 뭉개질 때 — 화소 글꼴 | Fusion Pixel 10px | https://github.com/TakWolf/fusion-pixel-font |
| 제목·로고·강조 | 검은고딕 (Black Han Sans) | https://fonts.google.com/specimen/Black+Han+Sans |
| 손글씨 | 나눔손글씨 펜 (Nanum Pen Script) | https://fonts.google.com/specimen/Nanum+Pen+Script |
| 붓글씨 | 나눔손글씨 붓 (Nanum Brush Script) | https://fonts.google.com/specimen/Nanum+Brush+Script |
| 본문 · 굵은 고딕 | Gothic A1 | https://fonts.google.com/specimen/Gothic+A1 |
| 본문 (한자 섞인 글) | Noto Sans CJK KR | https://github.com/notofonts/noto-cjk |
| 굵은 명조 | 송명 (Song Myung) | https://fonts.google.com/specimen/Song+Myung |
| 둥근 굵은 글씨 · 제목 | 주아 (Jua) | https://fonts.google.com/specimen/Jua |
| 화소 글꼴 | 물마루 (Mulmaru) | https://github.com/mushsooni/mulmaru |
| 화소 글꼴 | 움돋 13 (Umdot13) · 임글 모노 17 (Limgul Mono 17) | https://monadabxy.com |

Galmuri 는 크기(7·9·11·14)·굵기(Bold)·좁은꼴(Condensed)·고정폭(Mono)·Bitmap 판이 있다 — 원문 높이에 맞는 것을 고른다.

### 써 본 글꼴 중 OFL 이 아닌 것
키트 규칙은 OFL 글꼴이다. 아래는 다른 프로젝트에서 써 본 글꼴인데 OFL 이 아니다 — 쓰기 전에 사용자에게 묻고, 라이선스 파일을 같이 둔다.

| 쓰임 | 글꼴 | 라이선스 | 받는 곳 |
|---|---|---|---|
| 옛 도스 화면풍 명조·고딕·화소 | DOS 글꼴 (DOS명조·DOS고딕·DOS샘물·DOS이야기·삼삼·미래로) | MIT (출처 표기) | https://github.com/hurss/fonts |
| 화소 글꼴 (가는 둥근모) | 얇은둥근모 (ThinDungGeunMo) | 퍼블릭 도메인 (제작자 사칭 금지) | https://github.com/sawalk/Korean-Font-Change/releases/tag/Thin-0.1 |
| 화소 글꼴 | PF스타더스트 3.0 | 자체 라이선스 — 그림에 넣어 배포해도 되는지 확인 | 배포처에서 확인 |
| 화소 글꼴 | Silver | 자체 라이선스 — 확인 | 배포처에서 확인 |
| 둥근 굵은 글씨 | 배민 주아 (BMJUA) | 자체 라이선스 — 확인. 같은 글꼴의 OFL 판은 위의 「주아 (Jua)」 | https://www.woowahan.com/fonts |
| 명조·고딕 | KoPub World 바탕·돋움 | 자체 라이선스 — 확인 | 배포처에서 확인 |
| 명조 · 붓글씨 (견본으로만 써 봄) | 그레이스 세리프 · 국민대 성곡 · 이순신체 | 확인되지 않음 — 쓰지 않는 것이 기본 | 배포처에서 확인 |

제목·장식 글꼴이 더 필요하면 눈누(https://noonnu.cc) 에서 「OFL」 또는 「상업적 이용·임베딩·재배포 허용」이 모두 표시된 것만 고른다.
