"""인쇄 추상화 — 실행 환경 감지 후 자동 선택 (설계명세서 3.1).

- 리눅스(우노 Q · 데비안): lp (CUPS 드라이버리스 IPP, 프린터 'booth')
- 윈도우(대체 노트북):     SumatraPDF 무인 인쇄
- BOOTH_PRINT_DRY_RUN=1:  실제 인쇄 없이 data/printed/ 보관 (개발·리허설)
"""
import logging
import platform
import subprocess
from pathlib import Path

from . import config

log = logging.getLogger("booth.print")

last_error: str | None = None  # 관리 페이지 상태 표시용


def print_pdf(path: Path) -> tuple[bool, str | None]:
    """(성공 여부, 오류 메시지). last_error는 관리 페이지 표시용 최근값."""
    global last_error
    if config.DRY_RUN:
        log.info("DRY-RUN 인쇄 생략: %s", path)
        last_error = None
        return True, None
    try:
        if platform.system() == "Windows":
            cmd = [config.SUMATRA_PATH, "-print-to-default", "-silent", str(path)]
        else:
            cmd = [
                "lp",
                "-d", config.PRINTER_NAME,
                "-o", f"print-color-mode={config.PRINT_COLOR_MODE}",
                "-o", f"media={config.PAPER}",
                # 용지와 문서 크기가 달라도 멈추지 않고 맞춰 인쇄
                # (B5 도안 ↔ A4 용지는 비율이 거의 같아 왜곡 없음)
                "-o", "fit-to-page",
                str(path),
            ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=30)
        last_error = None
        log.info("인쇄 요청 완료: %s", path)
        return True, None
    except FileNotFoundError as e:
        err = f"인쇄 명령을 찾을 수 없음: {e}"
    except subprocess.CalledProcessError as e:
        err = f"인쇄 실패: {e.stderr.decode(errors='replace')[:200]}"
    except subprocess.TimeoutExpired:
        err = "인쇄 명령 시간 초과"
    last_error = err
    log.error(err)
    return False, err
