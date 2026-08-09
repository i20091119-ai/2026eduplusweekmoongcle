"""인쇄 추상화 — 실행 환경 감지 후 자동 선택 (설계명세서 3.1).

- 리눅스(우노 Q · 데비안): lp (CUPS 드라이버리스 IPP, 프린터 'booth')
- 윈도우(대체 노트북):     SumatraPDF 무인 인쇄
- BOOTH_PRINT_DRY_RUN=1:  실제 인쇄 없이 data/printed/ 보관 (개발·리허설)
"""
import logging
import os
import platform
import subprocess
from pathlib import Path

from . import config

log = logging.getLogger("booth.print")

last_error: str | None = None  # 관리 페이지 상태 표시용

_sumatra_cache: str | None = None


def _find_sumatra() -> str:
    """SumatraPDF 실행 파일 탐색 — 설치기 기본값이 버전에 따라 달라서 여러 위치 확인.

    우선순위: BOOTH_SUMATRA 환경변수 → Program Files(전체 사용자 설치)
    → AppData\\Local(현재 사용자 설치 · 최신 설치기 기본값) → 리포 폴더의 포터블.
    """
    global _sumatra_cache
    if _sumatra_cache:
        return _sumatra_cache
    candidates = [
        config.SUMATRA_PATH,
        r"C:\Program Files\SumatraPDF\SumatraPDF.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\SumatraPDF\SumatraPDF.exe"),
        str(config.BASE_DIR / "SumatraPDF.exe"),
    ]
    for c in candidates:
        if c and Path(c).exists():
            _sumatra_cache = c
            log.info("SumatraPDF 발견: %s", c)
            return c
    return config.SUMATRA_PATH  # 못 찾으면 기본값으로 시도 (에러 메시지에 경로가 남음)


def print_pdf(path: Path) -> tuple[bool, str | None]:
    """(성공 여부, 오류 메시지). last_error는 관리 페이지 표시용 최근값."""
    global last_error
    if config.DRY_RUN:
        log.info("DRY-RUN 인쇄 생략: %s", path)
        last_error = None
        return True, None
    try:
        if platform.system() == "Windows":
            cmd = [_find_sumatra(), "-print-to-default", "-print-settings", "fit", "-silent", str(path)]
        else:
            cmd = [
                "lp",
                "-d", config.PRINTER_NAME,
                "-o", f"print-color-mode={config.PRINT_COLOR_MODE}",
                "-o", f"media={config.PAPER}",
                # 용지와 문서 크기가 달라도 멈추지 않고 맞춰 인쇄
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
        detail = e.stderr.decode(errors="replace")[:200].strip()
        if not detail and platform.system() == "Windows":
            detail = "기본 프린터가 없거나 오프라인일 가능성 — 프린터 연결·기본 프린터 지정 확인"
        err = f"인쇄 실패 (종료코드 {e.returncode}): {detail}"
    except subprocess.TimeoutExpired:
        err = "인쇄 명령 시간 초과"
    last_error = err
    log.error(err)
    return False, err
