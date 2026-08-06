"""뭉클 부스 서버 — 코드 검증 · 대기열 · 인쇄 · WebSocket 호출 동기화.

역할 (설계명세서 3.1):
- 코드 검증 API (스마트폰 NFC 퀴즈에서 받은 세자리 정답코드)
- 도안 목록 · 스탬프 · 인쇄
- 좌석 점유 대기열(FIFO, 스테이션당 1) · 호출
- WebSocket 으로 키오스크 실시간 동기화
- 정적 서빙: /kiosk (키오스크) · /admin (관리) · /content (콘텐츠)
"""
import asyncio
import json
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, printing, queue_db, stamping

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
log = logging.getLogger("booth")

app = FastAPI(title="뭉클 부스 서버")
queue_db.init()


# ─────────────────────────── 콘텐츠 스캔 ───────────────────────────
# 서버 시작 시 + 요청 시마다 폴더를 읽는다 (파일 교체만으로 반영 — 3.4)

def load_codes() -> dict[str, str]:
    """content/quiz/quiz.json → {"코드": "몬스터 이름"}"""
    f = config.CONTENT_DIR / "quiz" / "quiz.json"
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8")).get("codes", {})
    except Exception as e:  # 손상된 JSON 이어도 서버는 계속 (무고장 우선)
        log.error("quiz.json 파싱 실패: %s", e)
        return {}


def list_dosan() -> list[dict]:
    """content/dosan/*.pdf — 파일명 = 화면 버튼 라벨."""
    d = config.CONTENT_DIR / "dosan"
    if not d.exists():
        return []
    return [
        {"file": p.name, "label": p.stem}
        for p in sorted(d.glob("*.pdf"))
    ]


def list_intro() -> list[str]:
    d = config.CONTENT_DIR / "intro"
    if not d.exists():
        return []
    exts = {".png", ".jpg", ".jpeg", ".svg", ".webp"}
    return [p.name for p in sorted(d.iterdir()) if p.suffix.lower() in exts]


def list_minigames() -> list[dict]:
    """content/minigame/<이름>/game.json 이 있는 폴더 = 게임 1개."""
    d = config.CONTENT_DIR / "minigame"
    games = []
    if not d.exists():
        return games
    for sub in sorted(d.iterdir()):
        meta_file = sub / "game.json"
        if sub.is_dir() and meta_file.exists() and (sub / "index.html").exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
            except Exception:
                meta = {}
            games.append({
                "id": sub.name,
                "title": meta.get("title", sub.name),
                "emoji": meta.get("emoji", "🎮"),
                "desc": meta.get("desc", ""),
                "url": f"/content/minigame/{sub.name}/index.html",
            })
    return games


# ─────────────────────────── WebSocket 허브 ───────────────────────────

class Hub:
    def __init__(self):
        self.clients: set[WebSocket] = set()
        self.lock = asyncio.Lock()

    async def join(self, ws: WebSocket):
        await ws.accept()
        async with self.lock:
            self.clients.add(ws)

    async def leave(self, ws: WebSocket):
        async with self.lock:
            self.clients.discard(ws)

    async def broadcast(self, message: dict):
        data = json.dumps(message, ensure_ascii=False)
        async with self.lock:
            dead = []
            for ws in self.clients:
                try:
                    await ws.send_text(data)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self.clients.discard(ws)


hub = Hub()


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await hub.join(ws)
    try:
        while True:
            await ws.receive_text()  # keepalive용 — 내용 무시
    except WebSocketDisconnect:
        pass
    finally:
        await hub.leave(ws)


# ─────────────────────────── API ───────────────────────────

class CodeIn(BaseModel):
    code: str


class CompleteIn(BaseModel):
    station: str
    dosan: str  # 파일명 (예: 우주비행사.pdf)


class StationIn(BaseModel):
    station: str | None = None


@app.get("/api/health")
def health():
    return {"ok": True, "role": "server"}


@app.get("/api/config")
def get_config():
    return {
        "stations": config.STATIONS,
        "called_seconds": config.CALLED_SCREEN_SECONDS,
        "brand_color": config.BRAND_COLOR,
    }


@app.post("/api/code/verify")
def verify_code(body: CodeIn):
    codes = load_codes()
    monster = codes.get(body.code.strip())
    if monster is None:
        return {"ok": False}
    return {"ok": True, "monster": monster}


@app.get("/api/dosan")
def get_dosan():
    return {"dosan": list_dosan()}


@app.get("/api/intro")
def get_intro():
    return {"intro": [f"/content/intro/{n}" for n in list_intro()]}


@app.get("/api/minigames")
def get_minigames():
    return {"minigames": list_minigames()}


@app.post("/api/complete")
async def complete(body: CompleteIn):
    """코드 확인 + 도안 선택 완료 → 번호 발급 · 스탬프 · 인쇄 · 대기열 등록."""
    if body.station not in config.STATIONS:
        raise HTTPException(400, "알 수 없는 스테이션")
    src = config.CONTENT_DIR / "dosan" / body.dosan
    if not src.exists() or src.suffix.lower() != ".pdf":
        raise HTTPException(404, "도안 파일 없음")

    # 좌석 확인 후에 번호 발급 (중복 시도로 번호가 소모되지 않도록)
    if queue_db.station_waiting(body.station):
        raise HTTPException(409, "이 자리는 이미 대기 중입니다")
    number = queue_db.next_number()
    if not queue_db.enqueue(body.station, number, body.dosan):
        raise HTTPException(409, "이 자리는 이미 대기 중입니다")

    # 스탬프 + 인쇄는 스레드에서 (이벤트 루프 비차단)
    def _stamp_and_print() -> bool:
        out = config.DATA_DIR / "printed" / f"{queue_db.today()}_{number:03d}.pdf"
        try:
            stamping.stamp_pdf(src, number, out)
        except Exception as e:
            printing.last_error = f"스탬프 실패: {e}"
            log.exception("스탬프 실패")
            return False
        return printing.print_pdf(out)

    printed = await asyncio.to_thread(_stamp_and_print)

    await hub.broadcast({"type": "queue", **queue_db.status()})
    return {"ok": True, "number": number, "printed": printed,
            "print_error": printing.last_error}


async def _do_call(row: dict | None):
    if row is None:
        return {"ok": False, "reason": "대기 중인 자리가 없습니다"}
    await hub.broadcast({
        "type": "called",
        "station": row["station"],
        "number": row["number"],
    })
    await hub.broadcast({"type": "queue", **queue_db.status()})
    log.info("호출: 스테이션 %s (No.%03d)", row["station"], row["number"])
    return {"ok": True, "station": row["station"], "number": row["number"]}


@app.post("/api/call")
async def call_next():
    """만들기존 아케이드 버튼 / 대형 호출 버튼 — 먼저 완료한 스테이션 호출."""
    return await _do_call(queue_db.call_next())


@app.post("/api/admin/call")
async def admin_call(body: StationIn):
    """관리 페이지 강제 호출 (특정 스테이션)."""
    if not body.station:
        raise HTTPException(400, "station 필요")
    return await _do_call(queue_db.call_station(body.station))


@app.post("/api/admin/reset")
async def admin_reset(body: StationIn):
    """상태 초기화 — 부재·오작동 예외 처리."""
    n = queue_db.reset_station(body.station)
    await hub.broadcast({"type": "queue", **queue_db.status()})
    return {"ok": True, "reset": n}


@app.get("/api/status")
def get_status():
    s = queue_db.status()
    s["print_error"] = printing.last_error
    s["dosan_count"] = len(list_dosan())
    s["code_count"] = len(load_codes())
    s["minigame_count"] = len(list_minigames())
    return s


@app.get("/")
def index():
    return RedirectResponse("/kiosk/")


# 정적 파일 (API 라우트보다 뒤에 마운트)
app.mount("/content", StaticFiles(directory=config.CONTENT_DIR), name="content")
app.mount("/admin", StaticFiles(directory=config.STATIC_DIR / "admin", html=True), name="admin")
app.mount("/kiosk", StaticFiles(directory=config.STATIC_DIR / "kiosk", html=True), name="kiosk")
