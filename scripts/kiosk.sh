#!/bin/sh
# 크로미움 키오스크 수동 실행 — 사용:  STATION=A SERVER=http://192.168.0.11 ./scripts/kiosk.sh
STATION="${STATION:-A}"
SERVER="${SERVER:-http://192.168.0.11}"
BROWSER="$(command -v chromium || command -v chromium-browser || command -v google-chrome)"
exec "$BROWSER" --kiosk --noerrdialogs --disable-infobars \
  --disable-session-crashed-bubble --autoplay-policy=no-user-gesture-required \
  "$SERVER/kiosk/?station=$STATION"
