"""LED 브리지 (Q1 · Q2 리눅스 측) — 서버 WebSocket 이벤트 → MCU 시리얼 명령.

이벤트 매핑:
  correct(자기 스테이션)  → 'C' (초록 플래시, MCU가 자동 복귀)
  called(자기 스테이션)   → 'W' (호출 웨이브) → called_seconds 후 'I'
  (연결 직후)             → 스테이션 색 설정 'A'/'B' + 'I'

환경변수:
  STATION          A | B                     (기본 A)
  BOOTH_SERVER     http://192.168.0.11       (기본값 — 역할 IP)
  BOOTH_MCU_PORT   /dev/ttyACM0              (우노 Q의 리눅스↔MCU 시리얼.
                                              보드에서 `ls /dev/ttyACM* /dev/ttyAMA*`로 확인)

의존성: pip install -r bridge/requirements.txt (pyserial · websockets)
서버·시리얼 어느 쪽이 끊겨도 재접속 루프 — 무고장 우선.
"""
import asyncio
import json
import logging
import os

import serial
import websockets

STATION = os.environ.get("STATION", "A").upper()
SERVER = os.environ.get("BOOTH_SERVER", "http://192.168.0.11").rstrip("/")
WS_URL = SERVER.replace("http", "ws", 1) + "/ws"
MCU_PORT = os.environ.get("BOOTH_MCU_PORT", "/dev/ttyACM0")
CALLED_SECONDS = int(os.environ.get("BOOTH_CALLED_SECONDS", "12"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s led_bridge %(message)s")
log = logging.getLogger()


def open_serial() -> serial.Serial | None:
    try:
        s = serial.Serial(MCU_PORT, 115200, timeout=0.1)
        log.info("MCU 연결: %s", MCU_PORT)
        return s
    except Exception as e:
        log.warning("MCU 포트 열기 실패(%s): %s — LED 없이 계속", MCU_PORT, e)
        return None


class Mcu:
    """시리얼이 죽어도 브리지는 계속 도는 래퍼."""
    def __init__(self):
        self.port = open_serial()

    def send(self, cmd: str):
        if self.port is None:
            self.port = open_serial()
        if self.port is None:
            return
        try:
            self.port.write(cmd.encode())
            log.info("MCU ← %r", cmd)
        except Exception as e:
            log.warning("시리얼 전송 실패: %s — 재연결 예정", e)
            try:
                self.port.close()
            except Exception:
                pass
            self.port = None


async def run():
    mcu = Mcu()
    idle_task: asyncio.Task | None = None

    async def back_to_idle():
        await asyncio.sleep(CALLED_SECONDS)
        mcu.send("I")

    while True:
        try:
            async with websockets.connect(WS_URL, ping_interval=20) as ws:
                log.info("서버 연결: %s (스테이션 %s)", WS_URL, STATION)
                mcu.send(STATION)  # 스테이션 색 설정
                mcu.send("I")
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                    except Exception:
                        continue
                    if msg.get("station") != STATION:
                        continue
                    if msg.get("type") == "correct":
                        mcu.send("C")
                    elif msg.get("type") == "called":
                        mcu.send("W")
                        if idle_task and not idle_task.done():
                            idle_task.cancel()
                        idle_task = asyncio.create_task(back_to_idle())
        except Exception as e:
            log.warning("서버 연결 끊김: %s — 3초 후 재시도", e)
            await asyncio.sleep(3)


if __name__ == "__main__":
    asyncio.run(run())
