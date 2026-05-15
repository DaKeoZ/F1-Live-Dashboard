"""
Cache SQLite pour les données F1 OpenF1.
Stocke télémétrie, circuit path et stints des sessions passées pour éviter
de re-poller OpenF1 à chaque consultation.
"""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))
DB_PATH = DATA_DIR / "f1_cache.db"


@contextmanager
def _db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with _db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS telemetry_cache (
                session_key   INTEGER NOT NULL,
                driver_number INTEGER NOT NULL,
                cached_at     TEXT    NOT NULL,
                PRIMARY KEY (session_key, driver_number)
            );

            CREATE TABLE IF NOT EXISTS telemetry_points (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                session_key   INTEGER NOT NULL,
                driver_number INTEGER NOT NULL,
                timestamp     TEXT    NOT NULL,
                speed         INTEGER,
                rpm           INTEGER,
                n_gear        INTEGER,
                throttle      INTEGER,
                brake         INTEGER,
                drs           INTEGER
            );

            CREATE INDEX IF NOT EXISTS idx_tel_sk_dn
                ON telemetry_points (session_key, driver_number);

            CREATE TABLE IF NOT EXISTS car_path_cache (
                session_key   INTEGER NOT NULL,
                driver_number INTEGER NOT NULL,
                cached_at     TEXT    NOT NULL,
                PRIMARY KEY (session_key, driver_number)
            );

            CREATE TABLE IF NOT EXISTS car_path_points (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                session_key   INTEGER NOT NULL,
                driver_number INTEGER NOT NULL,
                x             REAL    NOT NULL,
                y             REAL    NOT NULL,
                z             REAL    NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_path_sk_dn
                ON car_path_points (session_key, driver_number);

            CREATE TABLE IF NOT EXISTS stints_cache (
                session_key INTEGER PRIMARY KEY,
                cached_at   TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tyre_stints (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                session_key         INTEGER NOT NULL,
                driver_number       INTEGER NOT NULL,
                stint_number        INTEGER,
                lap_start           INTEGER,
                lap_end             INTEGER,
                compound            TEXT,
                tyre_age_at_start   INTEGER,
                compound_color      TEXT,
                compound_text_color TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_stints_sk_dn
                ON tyre_stints (session_key, driver_number);
        """)


# ── Telemetry ────────────────────────────────────────────────────────────────

def is_telemetry_cached(session_key: int, driver_number: int) -> bool:
    with _db() as conn:
        row = conn.execute(
            "SELECT 1 FROM telemetry_cache WHERE session_key=? AND driver_number=?",
            (session_key, driver_number),
        ).fetchone()
        return row is not None


def save_telemetry(session_key: int, driver_number: int, raw_points: list[dict]) -> None:
    with _db() as conn:
        conn.executemany(
            """INSERT OR IGNORE INTO telemetry_points
               (session_key, driver_number, timestamp, speed, rpm, n_gear, throttle, brake, drs)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    session_key,
                    driver_number,
                    str(p.get("date", "")),
                    int(p.get("speed") or 0),
                    int(p.get("rpm") or 0),
                    int(p.get("n_gear") or 0),
                    min(100, max(0, int(p.get("throttle") or 0))),
                    min(100, max(0, int(p.get("brake") or 0))),
                    p.get("drs"),
                )
                for p in raw_points
            ],
        )
        conn.execute(
            """INSERT OR REPLACE INTO telemetry_cache (session_key, driver_number, cached_at)
               VALUES (?, ?, ?)""",
            (session_key, driver_number, datetime.now(timezone.utc).isoformat()),
        )


def get_telemetry_raw(session_key: int, driver_number: int) -> list[dict]:
    with _db() as conn:
        rows = conn.execute(
            """SELECT timestamp, speed, rpm, n_gear, throttle, brake, drs
               FROM telemetry_points
               WHERE session_key=? AND driver_number=?
               ORDER BY timestamp""",
            (session_key, driver_number),
        ).fetchall()
        return [dict(r) for r in rows]


# ── Car path (circuit outline) ───────────────────────────────────────────────

def is_car_path_cached(session_key: int, driver_number: int) -> bool:
    with _db() as conn:
        row = conn.execute(
            "SELECT 1 FROM car_path_cache WHERE session_key=? AND driver_number=?",
            (session_key, driver_number),
        ).fetchone()
        return row is not None


def save_car_path(session_key: int, driver_number: int, raw_points: list[dict]) -> None:
    with _db() as conn:
        conn.executemany(
            """INSERT OR IGNORE INTO car_path_points (session_key, driver_number, x, y, z)
               VALUES (?, ?, ?, ?, ?)""",
            [
                (
                    session_key,
                    driver_number,
                    float(p.get("x") or 0),
                    float(p.get("y") or 0),
                    float(p.get("z") or 0),
                )
                for p in raw_points
            ],
        )
        conn.execute(
            """INSERT OR REPLACE INTO car_path_cache (session_key, driver_number, cached_at)
               VALUES (?, ?, ?)""",
            (session_key, driver_number, datetime.now(timezone.utc).isoformat()),
        )


def get_car_path_cached(session_key: int, driver_number: int) -> list[dict]:
    with _db() as conn:
        rows = conn.execute(
            """SELECT x, y, z FROM car_path_points
               WHERE session_key=? AND driver_number=?""",
            (session_key, driver_number),
        ).fetchall()
        return [dict(r) for r in rows]


# ── Tyre stints ──────────────────────────────────────────────────────────────

def is_stints_cached(session_key: int) -> bool:
    with _db() as conn:
        row = conn.execute(
            "SELECT 1 FROM stints_cache WHERE session_key=?", (session_key,)
        ).fetchone()
        return row is not None


def save_stints(session_key: int, stints: list[dict]) -> None:
    """stints: list of dicts with keys matching tyre_stints columns."""
    with _db() as conn:
        conn.executemany(
            """INSERT OR IGNORE INTO tyre_stints
               (session_key, driver_number, stint_number, lap_start, lap_end,
                compound, tyre_age_at_start, compound_color, compound_text_color)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    session_key,
                    int(s["driver_number"]),
                    int(s.get("stint_number") or 1),
                    int(s.get("lap_start") or 1),
                    int(s["lap_end"]) if s.get("lap_end") is not None else None,
                    s.get("compound"),
                    int(s.get("tyre_age_at_start") or 0),
                    s.get("compound_color", "#555555"),
                    s.get("compound_text_color", "#cccccc"),
                )
                for s in stints
            ],
        )
        conn.execute(
            "INSERT OR REPLACE INTO stints_cache (session_key, cached_at) VALUES (?, ?)",
            (session_key, datetime.now(timezone.utc).isoformat()),
        )


def get_stints_cached(session_key: int) -> list[dict]:
    with _db() as conn:
        rows = conn.execute(
            """SELECT driver_number, stint_number, lap_start, lap_end, compound,
                      tyre_age_at_start, compound_color, compound_text_color
               FROM tyre_stints WHERE session_key=?
               ORDER BY driver_number, stint_number""",
            (session_key,),
        ).fetchall()
        return [dict(r) for r in rows]
