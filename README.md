# 에듀플러스위크 뭉클 부스 — 우노 웹앱

제17회 2026 에듀플러스위크 미래교육박람회 (8/12~14 · 코엑스 A홀) 뭉클 부스의
**코드 입력 → 도안 자동 인쇄 → 좌석 대기 → 호출** 시스템.
아두이노 우노 Q 3대 + 캐논 646Cdw + 폐쇄망 기반 (시스템 설계명세서 v1.4 참조).

퀴즈 자체는 관람객 **스마트폰의 NFC 몬스터 퀴즈**(별도 제작)에서 풀고,
정답으로 받은 **4자리 코드**만 이 웹앱에 입력한다 — 두 시스템은 코드로만 연결되며 API 연동 없음.

## 구성

```
server/            FastAPI 서버 — 코드 검증 · 대기열(SQLite) · 스탬프 · 인쇄 · WebSocket
static/kiosk/      키오스크 웹앱 (Q1 · Q2 크로미움 전체화면, ?station=A|B)
static/admin/      관리 페이지 + 대형 호출 버튼 뷰 (call.html — Q3/노트북/스마트폰 대체용)
content/           콘텐츠 — 파일 교체만으로 반영, 코드 수정·재시작 불필요
  ├ dosan/         도안 PDF (B5 세로 · 흑백 라인아트 · 하단 30mm 비움)
  │                 동물/ 음식/ 감정/ 하위 폴더 = 도안 만들기 프로그램별 결과물
  ├ maker/         도안 만들기 프로그램 3종 설정 (personality · worldcup · emotion JSON)
  ├ quiz/          quiz.json — 통과 코드 목록 (현재 4자리 5종 · 몬스터 수와 무관)
  ├ intro/         뭉클 소개 이미지 (알아보기 + 대기 화면)
  └ minigame/      미니게임 6종 (폴더당 game.json + index.html)
arduino/           MCU 스케치 — quiz_led(Q1·Q2 LED 3종 연출) · button_caller(Q3 부저)
bridge/            리눅스↔MCU 브리지 — led_bridge(WS이벤트→시리얼) · button_bridge(PRESS→/api/call)
deploy/systemd/    부팅 자동 실행 유닛 (서버·키오스크·브리지 — 정전 자동 복구)
scripts/           개발 실행 · 키오스크 실행 스크립트
tools/             샘플 도안 생성기
docs/              인쇄테스트 절차서 · 스태프 운영 매뉴얼
```

## LED · 부저 연출 (MCU)

| 보드 | 스케치 | 연출 |
|---|---|---|
| Q1·Q2 | `arduino/quiz_led` | 대기: 스테이션 색 은은한 순환 / 정답: 초록 플래시 / 호출: 색 웨이브 (A 주황·B 파랑) |
| Q3 | `arduino/button_caller` | 버튼 LED 숨쉬기 점멸 · 눌림→호출 · 결과 피드백(초록/노랑/빨강) |

브리지 실행: `pip install -r bridge/requirements.txt` 후 `STATION=A python3 bridge/led_bridge.py` /
`python3 bridge/button_bridge.py` (운영은 systemd 유닛). 시리얼 포트는 `BOOTH_MCU_PORT`(기본 /dev/ttyACM0).

## 관람객 흐름 (부스 전체)

① 대기존에서 브로슈어 읽기 → ② 퀴즈존에서 스마트폰으로 NFC 피규어 퀴즈 → 4자리 코드 획득
→ ③ 키오스크에 코드 입력 + **도안 만들기** → 자동 인쇄 → ④ 자리 대기 → **띵동 호출** → 만들기존
→ ⑤ 클리커 제작 → AI(김토티) 심사 · 룰렛

**만들기존 부저(아케이드 버튼) = "자리 났어요" 신호.** 만들기를 마친 사람이 나가면
스태프가 1회 누름 → 먼저 완료하고 기다리던 스테이션 화면에 띵동.

### 키오스크 상태 머신

어트랙트 → 코드 입력(숫자 키패드, 자릿수는 quiz.json 코드 길이 자동 추종) → **도안 만들기(프로그램 3종 중 택 1)**
→ 인쇄(참여번호 블록 브랜드컬러 + 뭉클 QR 자동 스탬프)
→ 자리 대기(미니게임 6종 · 뭉클 이야기) → 띵동 호출(사운드 + 전체화면, 최우선 인터럽트) → 어트랙트

- 뭉클 알아보기(소개 슬라이드)는 어트랙트 화면의 선택 버튼 (브로슈어가 본 채널)
- 대기열: 좌석 점유 모델 — FIFO, 스테이션당 1명. 호출 버튼(`POST /api/call`) 1회 = 먼저 완료한 자리 호출
- 참여번호: 일자별 1부터 (기념·집계용)

### 도안 만들기 프로그램 3종 (`content/maker/*.json`으로 전부 교체 가능)

| 프로그램 | 방식 | 결과 |
|---|---|---|
| 🐾 나와 어울리는 동물은? | 성격검사 6문항 (2지선다) | 동물 4종 중 1 → 해당 도안 |
| 🍕 음식 이상형 월드컵 | 8강 토너먼트 | 우승 음식 도안 |
| 😊 내 감정을 담은 이모티콘 | 감정 6종 중 선택 | 감정 이모티콘 도안 |

결과마다 `content/dosan/<분류>/<이름>.pdf`가 연결되며, 프로그램 설정이 없으면 전체 목록 선택으로 폴백.

## 실행

```sh
pip install -r server/requirements.txt
BOOTH_PRINT_DRY_RUN=1 ./scripts/run_server.sh        # 개발 (인쇄 생략, :8000)
python3 tools/make_sample_dosan.py                    # 샘플 도안 생성 (최초 1회)
```

- 키오스크: `http://<서버>/kiosk/?station=A` (Q2는 `?station=B`)
- 관리: `http://<서버>/admin/` · 호출 버튼 뷰: `/admin/call.html`
- 운영 배포: `deploy/systemd/` 참조 (서버는 .11 고정 IP — "역할 IP" 원칙)

## 미니게임 8종 — 4×2 그리드 (모두 트랙볼 클릭 전용 · 1~2분 · 호출 시 즉시 중단)

| | 게임 | 방식 |
|---|---|---|
| 🧩 | 몬스터 짝맞추기 | 카드 12장 기억력 |
| 🔨 | 몬스터 잡기 | 두더지 잡기, 30초 |
| ❓ | 뭉클 O/X 퀴즈 | 부스 안내 복습 5문항 |
| 🎈 | 풍선 팡팡 | 떠오르는 풍선 클릭, 40초 |
| 🔍 | 다른 몬스터 찾기 | 틀린그림 찾기, 단계 상승 |
| 🧠 | 떡 주문 기억왕 | 주문 순서 외워 4지선다 회상 · 목숨 3개 |
| ⚖️ | 기우뚱 떡시루 | 떡 크기 눈대중으로 저울 수평 맞추기 (숫자 없음) |
| 🐰 | 껑충 달토끼 | L자 점프로 구름 위 떡 수집 — 막히면 종료 |

게임 추가: `content/minigame/<폴더>/`에 `game.json`(제목·이모지) + `index.html`만 넣으면 메뉴에 자동 노출.

## 환경변수 (역할·환경 구분)

| 변수 | 기본 | 용도 |
|---|---|---|
| `BOOTH_PRINTER` | `booth` | CUPS 프린터 이름 (646Cdw IPP 등록) |
| `BOOTH_PRINT_DRY_RUN` | `0` | `1`이면 인쇄 생략 (개발·리허설) |
| `BOOTH_PAPER` | `jis_b5_182x257mm` | 출력 용지 (B5 확정. ISO B5는 `iso_b5_176x250mm`) |
| `BOOTH_BRAND_COLOR` | `#F5573B` | 참여번호 블록 색 (뭉클 브랜드 컬러로 교체) |
| `BOOTH_QR_URL` | `https://moongcle.com` | 도안 하단 QR 링크 |
| `BOOTH_STATIONS` | `A,B` | 스테이션 목록 |
| `BOOTH_CALLED_SECONDS` | `12` | 호출 화면 표시 시간 |

프린터 등록(우노 Q/데비안): `lpadmin -p booth -E -v ipp://192.168.0.50/ipp/print -m everywhere`

## 비상 대체 (설계명세서 6장)

서버는 Python + 브라우저 + 네트워크 인쇄만 요구 → 노트북에서 동일 실행.
Q3(호출 버튼) 대체는 스마트폰/노트북으로 `/admin/call.html`.
윈도우 노트북 인쇄는 SumatraPDF 자동 선택 (`BOOTH_SUMATRA`로 경로 지정).
