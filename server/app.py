"""뭉클 부스 서버 — 코드 검증 · 대기열 · 인쇄 · WebSocket 호출 동기화.

역할 (설계명세서 3.1):
- 코드 검증 API (스마트폰 NFC 퀴즈에서 받은 4자리 정답코드)
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

def load_codes() -> set[str]:
    """content/quiz/quiz.json → 통과시킬 코드 집합.

    형식은 리스트(["0228", ...]) 권장 — 구버전 딕셔너리({"0228": "이름"})도 허용.
    """
    f = config.CONTENT_DIR / "quiz" / "quiz.json"
    if not f.exists():
        return set()
    try:
        codes = json.loads(f.read_text(encoding="utf-8")).get("codes", [])
        return set(codes)  # dict이면 키(코드)만 사용
    except Exception as e:  # 손상된 JSON 이어도 서버는 계속 (무고장 우선)
        log.error("quiz.json 파싱 실패: %s", e)
        return set()


DOSAN_EXTS = {".pdf", ".png"}  # PNG 도안은 인쇄 시 B5 페이지로 자동 조판


def list_dosan() -> list[dict]:
    """content/dosan/**/*.{pdf,png} — 파일명 = 결과 라벨, 하위 폴더 = 분류."""
    d = config.CONTENT_DIR / "dosan"
    if not d.exists():
        return []
    return [
        {
            "file": str(p.relative_to(d)),
            "label": p.stem,
            "category": p.parent.name if p.parent != d else "",
        }
        for p in sorted(d.rglob("*"))
        if p.is_file() and p.suffix.lower() in DOSAN_EXTS
    ]


def resolve_dosan(rel: str) -> Path | None:
    """도안 상대경로를 안전하게 해석 — dosan 폴더 밖 접근 차단."""
    d = (config.CONTENT_DIR / "dosan").resolve()
    try:
        p = (d / rel).resolve()
    except Exception:
        return None
    if p.is_file() and p.suffix.lower() in DOSAN_EXTS and p.is_relative_to(d):
        return p
    return None


def load_maker() -> dict:
    """content/maker/*.json — 도안 만들기 프로그램 설정 (파일 추가·삭제로 프로그램 구성)."""
    d = config.CONTENT_DIR / "maker"
    out = {}
    if not d.exists():
        return out
    for f in sorted(d.glob("*.json")):
        try:
            out[f.stem] = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            log.error("%s 파싱 실패: %s", f.name, e)
    return out


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
        # 락 안에서는 스냅샷만 — 한 클라이언트가 멈춰도 전체가 안 막히게
        async with self.lock:
            clients = list(self.clients)
        dead = []
        for ws in clients:
            try:
                await asyncio.wait_for(ws.send_text(data), timeout=2)
            except Exception:
                dead.append(ws)
        if dead:
            async with self.lock:
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
    station: str | None = None  # LED 연출용 — 어느 좌석에서 정답이 났는지


class CompleteIn(BaseModel):
    station: str
    dosan: str  # dosan 폴더 기준 상대경로 (예: 동물/여우.png)
    # 결과지 인쇄용 메타 (PNG 도안일 때 페이지에 함께 조판)
    title: str | None = None   # 결과 이름 (예: "INFP · 토끼")
    line: str | None = None    # 키워드 한 줄
    note: str | None = None    # 상세 설명 문단


class StationIn(BaseModel):
    station: str | None = None


@app.get("/api/health")
def health():
    return {"ok": True, "role": "server"}


@app.get("/api/config")
def get_config():
    codes = load_codes()
    lengths = sorted({len(c) for c in codes}) or [4]
    return {
        "stations": config.STATIONS,
        "called_seconds": config.CALLED_SCREEN_SECONDS,
        "brand_color": config.BRAND_COLOR,
        # 키패드 자릿수 — quiz.json 코드 길이를 따라감 (혼합 길이 지원)
        "code_length": lengths[-1],
        "code_lengths": lengths,
    }


@app.post("/api/code/verify")
async def verify_code(body: CodeIn):
    if body.code.strip() not in load_codes():
        return {"ok": False}
    if body.station:  # LED 브리지가 초록 플래시로 반응
        await hub.broadcast({"type": "correct", "station": body.station})
    return {"ok": True}


@app.get("/api/dosan")
def get_dosan():
    return {"dosan": list_dosan()}


@app.get("/api/maker")
def get_maker():
    return {"maker": load_maker()}


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
    src = resolve_dosan(body.dosan)
    if src is None:
        raise HTTPException(404, "도안 파일 없음")

    # 좌석 확인 후에 번호 발급 (중복 시도로 번호가 소모되지 않도록)
    if queue_db.station_waiting(body.station):
        raise HTTPException(409, "이 자리는 이미 대기 중입니다")
    number = queue_db.next_number()
    if not queue_db.enqueue(body.station, number, body.dosan):
        raise HTTPException(409, "이 자리는 이미 대기 중입니다")

    meta = {
        "title": (body.title or "").strip()[:60],
        "line": (body.line or "").strip()[:80],
        "note": (body.note or "").strip()[:400],
    }

    # 스탬프 + 인쇄는 스레드에서 (이벤트 루프 비차단) — 결과는 요청별로 격리
    def _stamp_and_print() -> tuple[bool, str | None]:
        out = config.DATA_DIR / "printed" / f"{queue_db.today()}_{number:03d}.pdf"
        try:
            stamping.stamp_pdf(src, number, out, meta)
        except Exception as e:
            err = f"스탬프 실패: {e}"
            printing.last_error = err
            log.exception("스탬프 실패")
            return False, err
        return printing.print_pdf(out)

    printed, print_error = await asyncio.to_thread(_stamp_and_print)

    await hub.broadcast({"type": "queue", **queue_db.status()})
    return {"ok": True, "number": number, "printed": printed,
            "print_error": print_error}


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
# content 전체를 열지 않는다 — quiz.json(정답 코드)이 노출되지 않도록 필요한 폴더만
(config.CONTENT_DIR / "intro").mkdir(parents=True, exist_ok=True)
(config.CONTENT_DIR / "minigame").mkdir(parents=True, exist_ok=True)
(config.CONTENT_DIR / "dosan").mkdir(parents=True, exist_ok=True)
app.mount("/content/intro", StaticFiles(directory=config.CONTENT_DIR / "intro"), name="intro")
app.mount("/content/minigame", StaticFiles(directory=config.CONTENT_DIR / "minigame"), name="minigame")
app.mount("/content/dosan", StaticFiles(directory=config.CONTENT_DIR / "dosan"), name="dosan")  # 결과 화면 미리보기용
app.mount("/admin", StaticFiles(directory=config.STATIC_DIR / "admin", html=True), name="admin")
app.mount("/kiosk", StaticFiles(directory=config.STATIC_DIR / "kiosk", html=True), name="kiosk")
