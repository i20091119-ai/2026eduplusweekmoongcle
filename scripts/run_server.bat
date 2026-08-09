@echo off
setlocal
cd /d "%~dp0.."

set PY=python
where python >nul 2>nul || set PY=py

rem Usage:
rem   run_server.bat                -> stations A,B / real printing
rem   run_server.bat dry            -> rehearsal (no printing)
rem   run_server.bat A,B,C          -> custom stations
rem   run_server.bat dry A,B,C,D    -> both
if /i "%1"=="dry" (
  set BOOTH_PRINT_DRY_RUN=1
  echo [DRY-RUN] No real printing - PDFs are saved to data\printed\
  if not "%2"=="" set BOOTH_STATIONS=%2
) else (
  if not "%1"=="" set BOOTH_STATIONS=%1
)
if defined BOOTH_STATIONS echo [STATIONS] %BOOTH_STATIONS%

if not exist .venv (
  echo [1/3] Creating virtual environment...
  %PY% -m venv .venv || goto :err
)

echo [2/3] Installing packages ^(first run only, 1-2 min^)...
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt || goto :err

echo [3/3] Starting server - DO NOT CLOSE THIS WINDOW
echo.
echo   This laptop : http://localhost:8000/kiosk/
echo   Kiosks      : http://LAPTOP_IP:8000/kiosk/?station=A  ^(B, C ... per station^)
echo   Admin       : http://LAPTOP_IP:8000/admin/
echo   ^(find LAPTOP_IP: run "ipconfig" in another cmd window^)
echo.
".venv\Scripts\python.exe" -m uvicorn server.app:app --host 0.0.0.0 --port 8000
pause
exit /b

:err
echo.
echo [ERROR] Setup failed.
echo  - Install Python 3.12 from python.org with "Add python.exe to PATH" checked
echo  - Then run this file again
pause
