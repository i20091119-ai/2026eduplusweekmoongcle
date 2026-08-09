@echo off
rem ── 뭉클 부스 서버 (윈도우 노트북용) ──────────────────────────
rem   더블클릭: 실제 인쇄 모드로 실행
rem   리허설:   run_server.bat dry   (인쇄 없이 data\printed\ 에 PDF만 보관)
chcp 65001 >nul
cd /d "%~dp0.."

where python >nul 2>nul
if errorlevel 1 (
  echo [오류] Python이 없습니다. python.org에서 3.11+ 설치 후 다시 실행하세요.
  echo        설치할 때 "Add python.exe to PATH" 반드시 체크!
  pause & exit /b 1
)

if not exist .venv (
  echo [1/3] 가상환경 생성 중...
  python -m venv .venv
)
call .venv\Scripts\activate.bat

echo [2/3] 의존성 설치 확인 중...
pip install -q -r requirements.txt

if /i "%1"=="dry" (
  set BOOTH_PRINT_DRY_RUN=1
  echo [리허설 모드] 실제 인쇄 없이 data\printed\ 에 PDF만 저장합니다.
)

echo [3/3] 서버 시작 — 이 창을 닫으면 부스가 멈춥니다!
echo.
echo   이 노트북에서:  http://localhost:8000/kiosk/
echo   태블릿에서:     http://이노트북IP:8000/kiosk/?station=A
echo   관리자:         http://이노트북IP:8000/admin/
echo   (IP 확인: 새 cmd 창에서 ipconfig)
echo.
python -m uvicorn server.app:app --host 0.0.0.0 --port 8000
pause
