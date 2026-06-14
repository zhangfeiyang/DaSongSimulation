"""SQLite persistence layer. Plain sqlite3, no ORM, JSON columns where handy."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS game_state (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    turn        INTEGER NOT NULL,
    year        INTEGER NOT NULL,
    month       INTEGER NOT NULL,
    player      TEXT NOT NULL,
    tech_state  TEXT         -- JSON: 科技树研究状态
);

CREATE TABLE IF NOT EXISTS factions (
    key       TEXT PRIMARY KEY,
    name      TEXT NOT NULL,
    name_en   TEXT,
    color     TEXT,
    is_player INTEGER DEFAULT 0,
    capital   TEXT,            -- "lat,lng"
    info      TEXT             -- short description
);

-- One stat snapshot per faction per turn.
CREATE TABLE IF NOT EXISTS faction_state (
    faction_key TEXT NOT NULL,
    turn        INTEGER NOT NULL,
    treasury    REAL,    -- 国库 (万贯)
    population   REAL,   -- 人口 (万人)
    economy     REAL,    -- 经济指数
    military    REAL,    -- 军力指数
    army        REAL,    -- 兵力 (万人)
    tech        REAL,    -- 科技 (0-100)
    stability   REAL,    -- 政治稳定 (0-100)
    welfare     REAL,    -- 民生/粮食 (0-100)
    relation    REAL,    -- 与玩家外交 (-100..100), 玩家自身=100
    note        TEXT,    -- 本回合该势力的状态简述
    at_war      INTEGER DEFAULT 0,   -- 是否与大宋处于交战状态
    PRIMARY KEY (faction_key, turn)
);

CREATE TABLE IF NOT EXISTS saves (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    created_at TEXT,
    turn       INTEGER,
    year       INTEGER,
    month      INTEGER,
    data       TEXT             -- JSON snapshot of the whole game
);

CREATE TABLE IF NOT EXISTS turn_log (
    turn       INTEGER PRIMARY KEY,
    year       INTEGER,
    month      INTEGER,
    policy     TEXT,        -- 玩家本回合政策
    narrative  TEXT,        -- LLM 推演叙事(文言)
    narrative_plain TEXT,   -- 推演叙事的白话文翻译
    events     TEXT,        -- JSON: 重大事件列表
    options    TEXT,        -- JSON: 下回合可选政策
    provider   TEXT,        -- 使用的 LLM provider
    created_at TEXT
);

-- 现行国策：已颁行、持续生效的国策账本。每回合推演都会带入，
-- LLM 据此持续计入其累积影响，并可新增 / 废止条目。
CREATE TABLE IF NOT EXISTS active_policies (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT NOT NULL,
    summary       TEXT,
    enacted_turn  INTEGER,     -- 颁行于第几回合
    enacted_label TEXT,        -- 如 "熙宁元年正月"
    coeffs        TEXT,        -- JSON: 各项国情的"每月影响系数"(可正可负), 如 {"economy":2,"treasury":150,"stability":-3}
    decay         REAL DEFAULT 0.9,  -- 月度衰减因子(0~1)，效果随时间递减
    ended_turn    INTEGER,     -- 废止于第几回合(用于回溯还原)
    status        TEXT DEFAULT 'active'   -- active | ended
);
"""


def connect() -> sqlite3.Connection:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db() -> None:
    conn = connect()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def is_initialised() -> bool:
    conn = connect()
    try:
        row = conn.execute("SELECT COUNT(*) AS c FROM factions").fetchone()
        return row["c"] > 0
    except sqlite3.OperationalError:
        return False
    finally:
        conn.close()


# ---- helpers -------------------------------------------------------------

def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


def jdump(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)


def jload(s: str | None, default: Any = None) -> Any:
    if not s:
        return default
    try:
        return json.loads(s)
    except Exception:
        return default
