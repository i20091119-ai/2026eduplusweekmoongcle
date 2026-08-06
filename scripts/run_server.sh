#!/bin/sh
# 개발/노트북 대체용 서버 실행 (기본 8000 포트 · 인쇄 DRY-RUN은 환경변수로)
#   BOOTH_PRINT_DRY_RUN=1 ./scripts/run_server.sh
cd "$(dirname "$0")/.."
exec python3 -m uvicorn server.app:app --host 0.0.0.0 --port "${PORT:-8000}" --reload
