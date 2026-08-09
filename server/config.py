"""부스 시스템 공통 설정 — 전부 환경변수로 재정의 가능 (3대 동일 이미지 + 역할은 환경변수 원칙)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONTENT_DIR = Path(os.environ.get("BOOTH_CONTENT", BASE_DIR / "content"))
DATA_DIR = Path(os.environ.get("BOOTH_DATA", BASE_DIR / "data"))
STATIC_DIR = BASE_DIR / "static"

DB_PATH = DATA_DIR / "booth.db"

# 인쇄
PRINTER_NAME = os.environ.get("BOOTH_PRINTER", "booth")
# 용지 — 도안 출력은 B5 (국내 B5 = JIS B5 182×257mm가 일반적. 프린터가 ISO B5로
# 잡으면 BOOTH_PAPER=iso_b5_176x250mm 로 변경)
PAPER = os.environ.get("BOOTH_PAPER", "jis_b5_182x257mm")
# 설계명세서 4장: 본문은 흑백 라인아트, 번호 블록만 브랜드 컬러 → 컬러 모드로 보내되 원본이 흑백
PRINT_COLOR_MODE = os.environ.get("BOOTH_PRINT_COLOR_MODE", "color")
# 개발/리허설용: 1이면 실제 인쇄 대신 로그만 남기고 data/printed/ 에 PDF 보관
DRY_RUN = os.environ.get("BOOTH_PRINT_DRY_RUN", "0") == "1"
SUMATRA_PATH = os.environ.get(
    "BOOTH_SUMATRA", r"C:\Program Files\SumatraPDF\SumatraPDF.exe"
)

# 도안 하단 스탬프
BRAND_COLOR = os.environ.get("BOOTH_BRAND_COLOR", "#7E212F")  # 뭉클 떡집 버건디
QR_URL = os.environ.get("BOOTH_QR_URL", "https://moongcle.com")
QR_CAPTION = os.environ.get("BOOTH_QR_CAPTION", "뭉클 더 알아보기")

# 스테이션 목록 (퀴즈존 좌석)
STATIONS = os.environ.get("BOOTH_STATIONS", "A,B").split(",")

# 호출 화면 표시 시간(초) — 이 시간이 지나면 키오스크가 어트랙트로 복귀
CALLED_SCREEN_SECONDS = int(os.environ.get("BOOTH_CALLED_SECONDS", "12"))

TZ = "Asia/Seoul"

DATA_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / "printed").mkdir(parents=True, exist_ok=True)
