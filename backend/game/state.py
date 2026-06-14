"""World-state read/write helpers and (re)seeding."""
from __future__ import annotations

import datetime as dt
import json
import math

import db
from config import START_YEAR, START_MONTH, PLAYER_FACTION, DATA_DIR
from game.seed_data import FACTIONS, NOTES
from game import territory

STAT_KEYS = ["treasury", "population", "economy", "military", "army",
             "tech", "stability", "welfare", "relation"]


def reset_world() -> None:
    """Drop all data and reseed the 1068 world. Also (re)writes factions.geojson."""
    conn = db.connect()
    conn.executescript("""
        DELETE FROM game_state;
        DELETE FROM factions;
        DELETE FROM faction_state;
        DELETE FROM turn_log;
        DELETE FROM active_policies;
    """)
    from game import tech as _tech
    conn.execute(
        "INSERT INTO game_state (id, turn, year, month, player, tech_state) "
        "VALUES (1, 0, ?, ?, ?, ?)",
        (START_YEAR, START_MONTH, PLAYER_FACTION, db.jdump(_tech.initial_state())),
    )
    for f in FACTIONS:
        conn.execute(
            "INSERT INTO factions (key, name, name_en, color, is_player, capital, info) "
            "VALUES (?,?,?,?,?,?,?)",
            (f["key"], f["name"], f["name_en"], f["color"],
             1 if f["is_player"] else 0, f["capital"], f["info"]),
        )
        s = f["stats"]
        conn.execute(
            "INSERT INTO faction_state (faction_key, turn, treasury, population, economy, "
            "military, army, tech, stability, welfare, relation, note, at_war) "
            "VALUES (?,0,?,?,?,?,?,?,?,?,?,?,0)",
            (f["key"], s["treasury"], s["population"], s["economy"], s["military"],
             s["army"], s["tech"], s["stability"], s["welfare"], s["relation"],
             NOTES.get(f["key"], "承平无事。")),
        )
    conn.commit()
    conn.close()

    territory.write()


def get_game_state() -> dict:
    conn = db.connect()
    row = conn.execute("SELECT * FROM game_state WHERE id=1").fetchone()
    conn.close()
    return dict(row)


def get_tech_state() -> dict:
    from game import tech as _tech
    conn = db.connect()
    row = conn.execute("SELECT tech_state FROM game_state WHERE id=1").fetchone()
    conn.close()
    ts = db.jload(row["tech_state"] if row else None, None)
    return ts if isinstance(ts, dict) else _tech.initial_state()


def save_tech_state(ts: dict) -> None:
    conn = db.connect()
    conn.execute("UPDATE game_state SET tech_state=? WHERE id=1", (db.jdump(ts),))
    conn.commit()
    conn.close()


def set_research(tech_id: str | None) -> dict:
    from game import tech as _tech
    ts = get_tech_state()
    if tech_id is None or _tech.is_available(tech_id, ts.get("researched", [])):
        if ts.get("current") != tech_id:
            ts["current"] = tech_id
            ts["progress"] = 0.0  # 切换研究目标则进度归零
        save_tech_state(ts)
    return ts


def get_factions_meta() -> dict[str, dict]:
    conn = db.connect()
    rows = conn.execute("SELECT * FROM factions").fetchall()
    conn.close()
    return {r["key"]: dict(r) for r in rows}


def get_states_at(turn: int) -> dict[str, dict]:
    """Latest stat snapshot for each faction at-or-before `turn`."""
    conn = db.connect()
    metas = {r["key"]: dict(r) for r in conn.execute("SELECT * FROM factions").fetchall()}
    out: dict[str, dict] = {}
    for key in metas:
        row = conn.execute(
            "SELECT * FROM faction_state WHERE faction_key=? AND turn<=? "
            "ORDER BY turn DESC LIMIT 1", (key, turn)).fetchone()
        if row:
            d = dict(row)
            d.update({k: metas[key][k] for k in
                      ("name", "name_en", "color", "is_player", "capital", "info")})
            out[key] = d
    conn.close()
    return out


def write_states(turn: int, states: dict[str, dict]) -> None:
    conn = db.connect()
    for key, s in states.items():
        conn.execute(
            "INSERT OR REPLACE INTO faction_state (faction_key, turn, treasury, population, "
            "economy, military, army, tech, stability, welfare, relation, note, at_war) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (key, turn, s["treasury"], s["population"], s["economy"], s["military"],
             s["army"], s["tech"], s["stability"], s["welfare"], s["relation"],
             s.get("note", ""), int(s.get("at_war", 0))),
        )
    conn.commit()
    conn.close()


def advance_calendar(year: int, month: int) -> tuple[int, int]:
    # 一回合 = 一年
    return year + 1, month


def date_for_turn(turn: int) -> tuple[int, int]:
    return START_YEAR + turn, START_MONTH


def rewind_to(target_turn: int) -> bool:
    """时间回溯：回到历史上的某一回合，丢弃其后的所有回合记录，
    并据存档信息还原国策账本（撤销其后颁布/废止的国策）。"""
    gs = get_game_state()
    if target_turn < 0 or target_turn >= gs["turn"]:
        return False
    y, m = date_for_turn(target_turn)
    conn = db.connect()
    conn.execute("DELETE FROM faction_state WHERE turn > ?", (target_turn,))
    conn.execute("DELETE FROM turn_log WHERE turn > ?", (target_turn,))
    # 其后才颁布的国策：尚不存在 -> 删除
    conn.execute("DELETE FROM active_policies WHERE enacted_turn >= ?", (target_turn,))
    # 其后才被废止的国策：当时仍在生效 -> 恢复为 active
    conn.execute("UPDATE active_policies SET status='active', ended_turn=NULL "
                 "WHERE status='ended' AND ended_turn >= ?", (target_turn,))
    conn.execute("UPDATE game_state SET turn=?, year=?, month=? WHERE id=1",
                 (target_turn, y, m))
    conn.commit()
    conn.close()
    return True


def get_last_turn_log() -> dict | None:
    conn = db.connect()
    row = conn.execute("SELECT * FROM turn_log ORDER BY turn DESC LIMIT 1").fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["events"] = db.jload(d.get("events"), [])
    d["options"] = db.jload(d.get("options"), [])
    return d


def write_turn_log(turn: int, year: int, month: int, policy: str,
                   narrative: str, narrative_plain: str, events: list, options: list,
                   provider: str) -> None:
    conn = db.connect()
    conn.execute(
        "INSERT OR REPLACE INTO turn_log (turn, year, month, policy, narrative, "
        "narrative_plain, events, options, provider, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (turn, year, month, policy, narrative, narrative_plain, db.jdump(events),
         db.jdump(options), provider, dt.datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    conn.close()


def get_history() -> list[dict]:
    conn = db.connect()
    rows = conn.execute("SELECT * FROM turn_log ORDER BY turn ASC").fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["events"] = db.jload(d.get("events"), [])
        d["options"] = db.jload(d.get("options"), [])
        out.append(d)
    return out


# ---- 现行国策 (active policy ledger) --------------------------------------

def get_active_policies(current_turn: int | None = None) -> list[dict]:
    if current_turn is None:
        current_turn = get_game_state()["turn"]
    conn = db.connect()
    rows = conn.execute(
        "SELECT * FROM active_policies WHERE status='active' ORDER BY enacted_turn ASC"
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["coeffs"] = db.jload(r["coeffs"], {})
        d["months"] = max(0, current_turn - (r["enacted_turn"] or 0))
        decay = r["decay"] if r["decay"] is not None else 0.9
        d["current_effect"] = _effect_at(d["coeffs"], decay, d["months"])
        # 长期(稳态)效力：steady 项永久保持、不衰减；标量项长期归零
        d["steady_effect"] = {k: round(s.get("steady", 0.0), 2)
                              for k, s in d["coeffs"].items()
                              if isinstance(s, dict) and abs(s.get("steady", 0.0)) >= 0.05}
        d["half_life"] = (round(math.log(0.5) / math.log(decay))
                          if 0 < decay < 1 else None)
        out.append(d)
    return out


def _effect_at(coeffs: dict, decay: float, months: int) -> dict:
    """当前这个月各项的实际(已演化)月度影响。
    - 标量 c：     effect = c * decay^(m-1)            —— 颁布初期较强、随后渐衰
    - {init,steady}：effect = steady + (init-steady)*decay^(m-1)
                     —— 由初期值平滑过渡到长期稳定值（可变号/可长期持续，用于研发、口岸等）"""
    if months < 1:
        return {}
    f = decay ** (months - 1)
    eff = {}
    for k, spec in coeffs.items():
        if isinstance(spec, dict):
            init = float(spec.get("init", spec.get("initial", 0)) or 0)
            steady = float(spec.get("steady", 0) or 0)
            eff[k] = round(steady + (init - steady) * f, 2)
        elif isinstance(spec, (int, float)):
            eff[k] = round(spec * f, 2)
    return eff


def add_active_policy(title: str, summary: str, coeffs: dict, decay: float,
                      enacted_turn: int, label: str) -> None:
    title = (title or "").strip()
    if not title:
        return
    conn = db.connect()
    dup = conn.execute(
        "SELECT 1 FROM active_policies WHERE status='active' AND title=?", (title,)).fetchone()
    if not dup:
        conn.execute(
            "INSERT INTO active_policies (title, summary, enacted_turn, enacted_label, "
            "coeffs, decay, status) VALUES (?,?,?,?,?,?, 'active')",
            (title, (summary or "").strip(), enacted_turn, label,
             db.jdump(coeffs or {}), float(decay) if decay else 0.9))
        conn.commit()
    conn.close()


def end_active_policies_by_title(titles: list[str], ended_turn: int) -> None:
    if not titles:
        return
    conn = db.connect()
    actives = conn.execute(
        "SELECT id, title FROM active_policies WHERE status='active'").fetchall()
    for t in titles:
        t = (t or "").strip()
        if not t:
            continue
        for row in actives:
            if t in row["title"] or row["title"] in t:
                conn.execute("UPDATE active_policies SET status='ended', ended_turn=? WHERE id=?",
                             (ended_turn, row["id"]))
    conn.commit()
    conn.close()


# ---- save / load ---------------------------------------------------------

_SNAPSHOT_TABLES = ["game_state", "factions", "faction_state", "turn_log", "active_policies"]


def _dump_game() -> dict:
    conn = db.connect()
    snap = {t: [dict(r) for r in conn.execute(f"SELECT * FROM {t}").fetchall()]
            for t in _SNAPSHOT_TABLES}
    conn.close()
    return snap


def save_game(name: str) -> dict:
    gs = get_game_state()
    snap = _dump_game()
    conn = db.connect()
    cur = conn.execute(
        "INSERT INTO saves (name, created_at, turn, year, month, data) VALUES (?,?,?,?,?,?)",
        (name.strip() or f"存档 {dt.datetime.now():%m-%d %H:%M}",
         dt.datetime.now().isoformat(timespec="seconds"),
         gs["turn"], gs["year"], gs["month"], db.jdump(snap)),
    )
    conn.commit()
    sid = cur.lastrowid
    conn.close()
    return {"id": sid}


def list_saves() -> list[dict]:
    conn = db.connect()
    rows = conn.execute(
        "SELECT id, name, created_at, turn, year, month FROM saves ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def load_game(save_id: int) -> bool:
    conn = db.connect()
    row = conn.execute("SELECT data FROM saves WHERE id=?", (save_id,)).fetchone()
    if not row:
        conn.close()
        return False
    snap = db.jload(row["data"], {})
    for t in _SNAPSHOT_TABLES:
        conn.execute(f"DELETE FROM {t}")
    for t in _SNAPSHOT_TABLES:
        for r in snap.get(t, []):
            cols = ",".join(r.keys())
            ph = ",".join("?" * len(r))
            conn.execute(f"INSERT INTO {t} ({cols}) VALUES ({ph})", list(r.values()))
    conn.commit()
    conn.close()
    return True


def delete_save(save_id: int) -> None:
    conn = db.connect()
    conn.execute("DELETE FROM saves WHERE id=?", (save_id,))
    conn.commit()
    conn.close()


def get_series(faction_key: str, keys: list[str]) -> list[dict]:
    """Time series of stats for charts."""
    conn = db.connect()
    rows = conn.execute(
        "SELECT * FROM faction_state WHERE faction_key=? ORDER BY turn ASC",
        (faction_key,)).fetchall()
    conn.close()
    return [{"turn": r["turn"], **{k: r[k] for k in keys}} for r in rows]
