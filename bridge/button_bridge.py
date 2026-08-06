"""호출 버튼 브리지 (Q3 리눅스 측) — MCU "PRESS" → 서버 /api/call → 결과 회신.

MCU 회신: 'K' 호출 성공 / 'E' 대기 없음 / 'X' 서버 오류
환경변수: BOOTH_SERVER (기본 http://192.168.0.11) · BOOTH_MCU_PORT (기본 /dev/ttyACM0)
의존성: pyserial (표준 urllib 사용 — websocket 불필요)
"""
import json
import logging
import os
import time
import urllib.request

import serial

SERVER = os.environ.get("BOOTH_SERVER", "http://192.168.0.11").rstrip("/")
MCU_PORT = os.environ.get("BOOTH_MCU_PORT", "/dev/ttyACM0")

logging.basicConfig(level=logging.INFO, format="%(asctime)s button_bridge %(message)s")
log = logging.getLogger()


def call_next() -> str:
    """서버 호출 → MCU 회신 문자."""
    try:
        req = urllib.request.Request(SERVER + "/api/call", method="POST")
        with urllib.request.urlopen(req, timeout=5) as r:
            j = json.load(r)
        if j.get("ok"):
            log.info("호출 성공: %s No.%03d", j["station"], j["number"])
            return "K"
        log.info("대기 없음")
        return "E"
    except Exception as e:
        log.error("서버 호출 실패: %s", e)
        return "X"


def main():
    while True:
        try:
            with serial.Serial(MCU_PORT, 115200, timeout=1) as port:
                log.info("MCU 연결: %s", MCU_PORT)
                buf = b""
                while True:
                    chunk = port.read(64)
                    if not chunk:
                        continue
                    buf += chunk
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        if line.strip() == b"PRESS":
                            log.info("버튼 눌림")
                            port.write(call_next().encode())
        except Exception as e:
            log.warning("시리얼 오류: %s — 3초 후 재연결", e)
            time.sleep(3)


if __name__ == "__main__":
    main()
