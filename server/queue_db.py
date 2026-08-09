"""좌석 점유 대기 모델의 FIFO 큐 + 일자별 참여번호 카운터 (SQLite).

설계명세서 3.3:
- FIFO 큐, 최대 스테이션당 1항목 (좌석 = 슬롯)
- 먼저 완료한 스테이션부터 호출
- 번호는 일자별 1부터 증가 — 기념·집계용
"""
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

from . import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day TEXT NOT NULL,
    station TEXT NOT NULL,
    number INTEGER NOT NULL,
    dosan TEXT,
    status TEXT NOT NULL DEFAULT 'waiting',  -- waiting | called | reset
    created_at TEXT NOT NULL,
    called_at TEXT
);
CREATE TABLE IF NOT EXISTS counters (
    day TEXT PRIMARY KEY,
    value INTEGER NOT NULL
);
"""


def today() -> str:
    return datetime.now(ZoneInfo(config.TZ)).strftime("%Y-%m-%d")


def _now() -> str:
    return datetime.now(ZoneInfo(config.TZ)).isoformat(timespec="seconds")


@contextmanager
def _db():
    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init():
    with _db() as con:
        con.executescript(_SCHEMA)
        try:  # 재인쇄용 결과지 메타 (기존 DB 마이그레이션)
            con.execute("ALTER TABLE queue ADD COLUMN meta TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass


def next_number() -> int:
    """일자별 참여번호 발급 (1부터)."""
    day = today()
    with _db() as con:
        con.execute(
            "INSERT INTO counters(day, value) VALUES(?, 0) "
            "ON CONFLICT(day) DO NOTHING",
            (day,),
        )
        con.execute("UPDATE counters SET value = value + 1 WHERE day = ?", (day,))
        row = con.execute("SELECT value FROM counters WHERE day = ?", (day,)).fetchone()
        return row["value"]


def station_waiting(station: str) -> bool:
    with _db() as con:
        return con.execute(
            "SELECT 1 FROM queue WHERE station = ? AND status = 'waiting'",
            (station,),
        ).fetchone() is not None


def enqueue(station: str, number: int, dosan: str, meta: str = "") -> bool:
    """스테이션을 대기열에 등록. 이미 대기 중이면 False (좌석당 1명 원칙)."""
    with _db() as con:
        dup = con.execute(
            "SELECT 1 FROM queue WHERE station = ? AND status = 'waiting'",
            (station,),
        ).fetchone()
        if dup:
            return False
        con.execute(
            "INSERT INTO queue(day, station, number, dosan, status, created_at, meta) "
            "VALUES(?,?,?,?, 'waiting', ?, ?)",
            (today(), station, number, dosan, _now(), meta),
        )
        return True


def recent(limit: int = 8) -> list[dict]:
    """오늘 발급된 최근 항목 — 재인쇄용 (번호·도안·메타)."""
    with _db() as con:
        return [
            dict(r)
            for r in con.execute(
                "SELECT number, station, dosan, meta, status FROM queue "
                "WHERE day = ? ORDER BY id DESC LIMIT ?",
                (today(), limit),
            )
        ]


def call_next() -> dict | None:
    """먼저 완료한(가장 오래된) 대기 스테이션을 호출 처리."""
    with _db() as con:
        row = con.execute(
            "SELECT * FROM queue WHERE status = 'waiting' ORDER BY id LIMIT 1"
        ).fetchone()
        if not row:
            return None
        con.execute(
            "UPDATE queue SET status = 'called', called_at = ? WHERE id = ?",
            (_now(), row["id"]),
        )
        return dict(row)


def call_station(station: str) -> dict | None:
    """관리 페이지 강제 호출 — 특정 스테이션 지정."""
    with _db() as con:
        row = con.execute(
            "SELECT * FROM queue WHERE status = 'waiting' AND station = ? "
            "ORDER BY id LIMIT 1",
            (station,),
        ).fetchone()
        if not row:
            return None
        con.execute(
            "UPDATE queue SET status = 'called', called_at = ? WHERE id = ?",
            (_now(), row["id"]),
        )
        return dict(row)


def reset_station(station: str | None = None) -> int:
    """대기 상태 초기화 (관리 페이지 예외 처리). station=None이면 전체."""
    with _db() as con:
        if station:
            cur = con.execute(
                "UPDATE queue SET status = 'reset' WHERE status = 'waiting' AND station = ?",
                (station,),
            )
        else:
            cur = con.execute(
                "UPDATE queue SET status = 'reset' WHERE status = 'waiting'"
            )
        return cur.rowcount


def status() -> dict:
    day = today()
    with _db() as con:
        waiting = [
            dict(r)
            for r in con.execute(
                "SELECT station, number, dosan, created_at FROM queue "
                "WHERE status = 'waiting' ORDER BY id"
            )
        ]
        row = con.execute("SELECT value FROM counters WHERE day = ?", (day,)).fetchone()
        called_today = con.execute(
            "SELECT COUNT(*) c FROM queue WHERE day = ? AND status = 'called'", (day,)
        ).fetchone()["c"]
        per_day = [
            dict(r)
            for r in con.execute(
                "SELECT day, value AS total FROM counters ORDER BY day"
            )
        ]
    return {
        "day": day,
        "waiting": waiting,
        "today_participants": row["value"] if row else 0,
        "today_called": called_today,
        "per_day": per_day,
    }
