"""The turn engine: load state -> prompt LLM -> apply deltas -> persist -> advance."""
from __future__ import annotations

import copy

from config import load_llm_config, PLAYER_FACTION
from llm.client import complete, extract_json, LLMError
from llm.prompts import SYSTEM_PROMPT, build_user_message
from game import state as st
from game import sim
from game import tech as techmod
from game import war

# stat -> (min, max)  ; None means unbounded on that side
BOUNDS = {
    "treasury": (-100000, None),
    "population": (0, None),
    "economy": (0, None),
    "military": (0, None),
    "army": (0, None),
    "tech": (0, 100),
    "stability": (0, 100),
    "welfare": (0, 100),
    "relation": (-100, 100),
}
DELTA_KEYS = list(BOUNDS.keys())


def _resolve_decay(np: dict) -> float:
    """优先用直观的 half_life(成熟半衰期, 月)换算衰减；否则用 decay。
    half_life 越大 = 越"大后期"(效果积累越慢、越晚显威)。"""
    hl = np.get("half_life", np.get("halflife"))
    if isinstance(hl, (int, float)) and hl > 0:
        decay = 0.5 ** (1.0 / float(hl))
    else:
        d = np.get("decay")
        decay = float(d) if isinstance(d, (int, float)) else 0.9
    return min(0.995, max(0.30, decay))   # 半衰期约 2 个月 ~ 138 个月


def _sanitize_coeffs(raw: dict) -> dict:
    """Accept per-stat coefficients as a scalar, or a {init, steady} profile
    (for policies whose effect ramps / pays off over time)."""
    out: dict = {}
    for k, v in (raw or {}).items():
        if k not in BOUNDS and k != "science":   # science 不是国情数值，而是科技点/月加成
            continue
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            out[k] = float(v)
        elif isinstance(v, dict):
            init = v.get("init", v.get("initial"))
            steady = v.get("steady", v.get("long_run", v.get("long")))
            if isinstance(init, (int, float)) or isinstance(steady, (int, float)):
                out[k] = {"init": float(init) if isinstance(init, (int, float)) else 0.0,
                          "steady": float(steady) if isinstance(steady, (int, float)) else 0.0}
    return out


def _clamp(key: str, val: float) -> float:
    lo, hi = BOUNDS[key]
    if lo is not None:
        val = max(lo, val)
    if hi is not None:
        val = min(hi, val)
    return round(val, 2)


def run_turn(policy_text: str, chosen_options: list[str]) -> dict:
    cfg = load_llm_config()
    gs = st.get_game_state()
    turn, year, month = gs["turn"], gs["year"], gs["month"]

    states = st.get_states_at(turn)

    # Merge any chosen option titles into the free-text policy.
    policy = policy_text.strip()
    if chosen_options:
        chosen = "；".join(o.strip() for o in chosen_options if o.strip())
        policy = (policy + "\n采纳建议：" + chosen).strip() if policy else "采纳建议：" + chosen

    history = st.get_history()
    history_brief = [h["narrative"][:80] for h in history if h.get("narrative")]

    active = st.get_active_policies(turn)
    user_msg = build_user_message(turn, year, month, states, policy, history_brief, active)

    try:
        raw = complete(SYSTEM_PROMPT, user_msg, cfg)
        result = extract_json(raw)
    except LLMError as e:
        raise
    if not isinstance(result, dict):
        raise LLMError("LLM 返回的不是 JSON 对象")

    changes = result.get("changes", {}) or {}

    # Apply deltas to produce next-turn snapshot.
    new_states = copy.deepcopy(states)

    # (1) 持续性国策：按"影响系数 × 时间衰减"公式自动累计到大宋（无需 LLM 逐月重算）。
    ongoing: dict[str, float] = {}
    for p in active:
        for k, v in (p.get("current_effect") or {}).items():
            if k in BOUNDS:
                ongoing[k] = ongoing.get(k, 0.0) + v
    song_state = new_states.get(PLAYER_FACTION)
    if song_state:
        for k, v in ongoing.items():
            song_state[k] = _clamp(k, float(song_state[k]) + v)

    # (2) LLM 给出的本月即时影响（新政冲击 + 事件 + 列国反应）。
    for fkey, delta in changes.items():
        if fkey not in new_states or not isinstance(delta, dict):
            continue
        s = new_states[fkey]
        for k in DELTA_KEYS:
            if k in delta and isinstance(delta[k], (int, float)):
                s[k] = _clamp(k, float(s[k]) + float(delta[k]))
        if delta.get("note"):
            s["note"] = str(delta["note"])[:160]

    # (3) 确定性经济/军事结算（所有势力）：国库收支、军力量化、破产连锁。
    sim_info = sim.apply_monthly(new_states, PLAYER_FACTION)

    # (4) 科技树研究推进（玩家）：基础速率 + 现行国策的科技点加成；完成则落效果。
    science_bonus = techmod.policy_science_bonus(active)
    tech_info = techmod.advance_research(new_states.get(PLAYER_FACTION), science_bonus)

    # final clamp across all stats
    for s in new_states.values():
        for k in DELTA_KEYS:
            s[k] = _clamp(k, float(s[k]))

    # The player's own diplomatic "relation" to itself stays pinned at 100.
    if PLAYER_FACTION in new_states:
        new_states[PLAYER_FACTION]["relation"] = 100

    next_turn = turn + 1
    st.write_states(next_turn, new_states)

    new_year, new_month = st.advance_calendar(year, month)
    conn = st.db.connect()
    conn.execute("UPDATE game_state SET turn=?, year=?, month=? WHERE id=1",
                 (next_turn, new_year, new_month))
    conn.commit()
    conn.close()

    events = result.get("events", []) or []
    options = result.get("options", []) or []
    narrative = result.get("narrative", "") or ""
    narrative_plain = result.get("narrative_plain", "") or ""

    st.write_turn_log(next_turn, year, month, policy, narrative, narrative_plain,
                      events, options, cfg.provider)

    # update the 现行国策 ledger: add new standing policies, retire ended ones
    pu = result.get("policy_updates", {}) or {}
    label = f"{year}年{month}月"
    for np in (pu.get("new_policies") or []):
        if isinstance(np, dict):
            coeffs = _sanitize_coeffs(np.get("coeffs") or {})
            st.add_active_policy(np.get("title", ""), np.get("summary", ""),
                                 coeffs, _resolve_decay(np), turn, label)
    st.end_active_policies_by_title(pu.get("ended_policies") or [], turn)

    # LLM 自主裁决的领土变更（占据无主之地 / 吞并败国）→ 重绘地图
    map_changed = False
    for ch in (result.get("territory_changes") or []):
        if isinstance(ch, dict) and ch.get("owner") and ch.get("bbox"):
            if war.annex_area(ch["owner"], ch["bbox"], ch.get("name", "")):
                map_changed = True

    return {
        "turn": next_turn,
        "year": year, "month": month,           # the month that was just simulated
        "now_year": new_year, "now_month": new_month,
        "provider": cfg.provider,
        "policy": policy,
        "narrative": narrative,
        "narrative_plain": narrative_plain,
        "events": events,
        "options": options,
        "difficulty": result.get("difficulty", ""),
        "verdict": result.get("verdict", ""),
        "changes": changes,
        "ongoing": {k: round(v, 2) for k, v in ongoing.items() if abs(v) >= 0.05},
        "active_policies": st.get_active_policies(next_turn),
        "budget": sim_info.get("player_budget"),
        "bankrupts": sim_info.get("bankrupts"),
        "tech_completed": tech_info.get("completed"),
        "map_changed": map_changed,
        "territory_changes": result.get("territory_changes") or [],
    }
