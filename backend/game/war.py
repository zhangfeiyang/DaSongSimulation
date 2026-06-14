"""战争与议和：军力归零=被占领；议和可割地(按面积改地图)+赔款(改两国国库)。"""
from __future__ import annotations

import json

from config import DATA_DIR


DEF_BONUS = 1.25       # 守土(本土作战)优势
WAR_COST_K = 15.0      # 军费：每投入 1 万兵 的战役开销(万贯)
INTENSITY = {"raid": 0.35, "battle": 0.6, "allout": 0.9}   # 袭扰/会战/决战


def launch_campaign(target_key: str, commit_army: float, intensity: str = "battle") -> dict:
    """纯公式化战役结算：大宋出兵讨伐 target_key。
    依双方 战力 = 兵力 × 武器系数(科技) × 民族战力 × 士气，加守方本土优势与战场偶然，
    算出胜负比，按比折算双方伤亡、军费、赔损、外交恶化；守方军力归零即被占领。"""
    import random
    from game import state as st
    from game import sim

    gs = st.get_game_state()
    turn = gs["turn"]
    states = st.get_states_at(turn)
    if target_key not in states or states[target_key].get("is_player"):
        return {"ok": False, "error": "无效的攻击对象"}

    song = states["song"]
    foe = states[target_key]
    commit = max(1.0, min(float(commit_army), song["army"]))
    inten = INTENSITY.get(intensity, 0.6)
    rng = random.Random()

    wf = sim.weapon_factor
    morale = lambda s: 0.7 + 0.3 * s["stability"] / 100.0
    cp_a = (commit * wf(song["tech"]) * sim.QUALITY.get("song", 0.6)
            * morale(song) * rng.uniform(0.85, 1.15))
    cp_d = (foe["army"] * wf(foe["tech"]) * sim.QUALITY.get(target_key, 0.6)
            * DEF_BONUS * morale(foe) * rng.uniform(0.85, 1.15))
    r = cp_a / (cp_a + cp_d) if (cp_a + cp_d) > 0 else 0.5     # 宋方胜率(0~1)

    foe_losses = min(foe["army"] * 0.95, foe["army"] * r * inten * 1.4)
    song_losses = min(commit * 0.95, commit * (1 - r) * inten * 1.4)

    foe["army"] = max(0.0, foe["army"] - foe_losses)
    song["army"] = max(0.0, song["army"] - song_losses)
    war_cost = round(commit * WAR_COST_K * (0.6 + inten), 1)
    song["treasury"] = round(song["treasury"] - war_cost, 1)
    foe["treasury"] = round(foe["treasury"] - foe_losses * 8, 1)   # 兵燹之损
    foe["relation"] = max(-100, min(100, foe.get("relation", 0) - 30))
    foe["stability"] = max(0.0, foe["stability"] - 3)
    song["stability"] = max(0.0, song["stability"] - 1)            # 兵疲民困

    song["military"] = sim.expected_military("song", song)
    foe["military"] = sim.expected_military(target_key, foe)
    foe["at_war"] = 1                                  # 进入交战状态
    occupied = foe["army"] <= 0.5 or foe["military"] <= 0.5

    outcome = ("大捷" if r > 0.62 else "胜" if r > 0.52 else
               "相持" if r >= 0.45 else "败绩" if r > 0.38 else "大败")
    foe["note"] = (f"为宋所破，军覆都危、社稷将倾。" if occupied
                   else f"与宋交兵，折兵{round(foe_losses)}万，国势受挫。")
    song["note"] = f"出兵{round(commit)}万伐{foe['name']}，{outcome}，折损{round(song_losses)}万。"
    st.write_states(turn, {"song": song, target_key: foe})

    return {
        "ok": True, "target": foe["name"], "outcome": outcome,
        "win_ratio": round(r, 3),
        "song_losses": round(song_losses, 1), "foe_losses": round(foe_losses, 1),
        "war_cost": war_cost,
        "song_army": round(song["army"], 1), "foe_army": round(foe["army"], 1),
        "song_military": song["military"], "foe_military": foe["military"],
        "occupied": occupied,
        "cp_song": round(cp_a, 1), "cp_foe": round(cp_d, 1),
    }


def occupied_factions(states: dict[str, dict]) -> list[str]:
    """军力降至≈0 视为被占领/灭亡。"""
    return [k for k, s in states.items()
            if not s.get("is_player") and s.get("military", 0) <= 0.5]


# ---- 割地：按面积把战败方一部分领土转给战胜方，并重绘地图 ----

def _area_cut(geom, frac: float, from_west: bool):
    """沿经度方向二分，切出战败方约 frac 面积的一块(靠战胜方一侧)。"""
    from shapely.geometry import box
    minx, miny, maxx, maxy = geom.bounds
    total = geom.area
    if total <= 0:
        return None, geom
    target = total * max(0.0, min(0.95, frac))
    lo, hi = minx, maxx
    for _ in range(24):
        mid = (lo + hi) / 2
        if from_west:
            piece = geom.intersection(box(minx - 1, miny - 1, mid, maxy + 1))
        else:
            piece = geom.intersection(box(mid, miny - 1, maxx + 1, maxy + 1))
        if piece.area < target:
            if from_west:
                lo = mid
            else:
                hi = mid
        else:
            if from_west:
                hi = mid
            else:
                lo = mid
    mid = (lo + hi) / 2
    if from_west:
        ceded = geom.intersection(box(minx - 1, miny - 1, mid, maxy + 1))
    else:
        ceded = geom.intersection(box(mid, miny - 1, maxx + 1, maxy + 1))
    remaining = geom.difference(ceded)
    return ceded, remaining


def cede_territory(loser_key: str, winner_key: str, frac: float) -> float:
    """把战败方 frac 比例的领土割让给战胜方，重写 factions.geojson。返回实际割让面积占比。"""
    try:
        from shapely.geometry import shape, mapping
        from shapely.ops import unary_union
    except Exception:
        return 0.0
    path = DATA_DIR / "factions.geojson"
    gj = json.loads(path.read_text(encoding="utf-8"))
    feats = gj["features"]
    loser = next((f for f in feats if f["properties"]["key"] == loser_key), None)
    winner = next((f for f in feats if f["properties"]["key"] == winner_key), None)
    if not loser or not winner:
        return 0.0

    lg = shape(loser["geometry"]).buffer(0)
    wg = shape(winner["geometry"]).buffer(0)
    if lg.is_empty or lg.area <= 0:
        return 0.0
    from_west = wg.centroid.x <= lg.centroid.x      # 战胜方在西侧则割西部
    ceded, remaining = _area_cut(lg, frac, from_west)
    if ceded is None or ceded.is_empty:
        return 0.0
    moved = ceded.area / lg.area

    winner["geometry"] = mapping(unary_union([wg, ceded]).simplify(0.05, True))
    if remaining.is_empty or remaining.area < lg.area * 0.02:
        feats.remove(loser)                         # 全境沦陷
    else:
        loser["geometry"] = mapping(remaining.simplify(0.05, True))
    path.write_text(json.dumps(gj, ensure_ascii=False), encoding="utf-8")
    return round(moved, 3)


def annex_area(owner_key: str, bbox: list, name: str = "") -> bool:
    """把一个经纬度方框内的陆地并入 owner 的领土（从原属势力划走；无主之地则直接归入），
    并重绘 factions.geojson。用于 LLM 裁决的扩张（如占据台湾等无主之地、吞并败国疆土）。"""
    try:
        from shapely.geometry import shape, box, mapping
        from shapely.ops import unary_union
    except Exception:
        return False
    if not (isinstance(bbox, (list, tuple)) and len(bbox) == 4):
        return False
    minx, miny, maxx, maxy = [float(v) for v in bbox]
    if maxx <= minx or maxy <= miny:
        return False
    region = box(minx, miny, maxx, maxy)

    from game.seed_data import FACTIONS
    color = next((f["color"] for f in FACTIONS if f["key"] == owner_key), "#888888")
    pname = next((f["name"] for f in FACTIONS if f["key"] == owner_key), owner_key)

    world = json.loads((DATA_DIR / "world.geojson").read_text(encoding="utf-8"))
    land = [shape(f["geometry"]).buffer(0) for f in world["features"]
            if shape(f["geometry"]).bounds and box(*shape(f["geometry"]).bounds).intersects(region)]
    if not land:
        return False
    gained = unary_union(land).intersection(region)
    if gained.is_empty or gained.area <= 0:
        return False

    gj = json.loads((DATA_DIR / "factions.geojson").read_text(encoding="utf-8"))
    feats = gj["features"]
    # 从其他势力划走该片土地
    for f in list(feats):
        if f["properties"]["key"] == owner_key:
            continue
        g = shape(f["geometry"]).buffer(0)
        if g.intersects(gained):
            rem = g.difference(gained)
            if rem.is_empty or rem.area < g.area * 0.02:
                feats.remove(f)
            else:
                f["geometry"] = mapping(rem.simplify(0.05, True))
    # 并入 owner（已有则合并，没有则新建要素）
    own = next((f for f in feats if f["properties"]["key"] == owner_key), None)
    if own:
        own["geometry"] = mapping(unary_union([shape(own["geometry"]).buffer(0), gained]).simplify(0.05, True))
    else:
        feats.append({"type": "Feature",
                      "properties": {"key": owner_key, "name": pname, "color": color,
                                     "is_player": owner_key == "song"},
                      "geometry": mapping(gained.simplify(0.05, True))})
    (DATA_DIR / "factions.geojson").write_text(json.dumps(gj, ensure_ascii=False), encoding="utf-8")
    return True


def negotiate_peace(faction_key: str, cede_fraction: float, indemnity: float,
                    song_pays: bool = False) -> dict:
    """议和：赔款改两国国库；割地改地图。默认大宋为战胜方(对方割地赔款)。
    song_pays=True 表示大宋战败，向对方割地赔款。"""
    from game import state as st
    gs = st.get_game_state()
    turn = gs["turn"]
    states = st.get_states_at(turn)
    if faction_key not in states or states[faction_key].get("is_player"):
        return {"ok": False, "error": "无效的议和对象"}

    song = states["song"]
    other = states[faction_key]
    indemnity = max(0.0, float(indemnity))
    cede_fraction = max(0.0, min(0.9, float(cede_fraction)))

    if song_pays:   # 大宋战败：宋赔款割地给对方
        song["treasury"] -= indemnity
        other["treasury"] += indemnity
        winner, loser = faction_key, "song"
    else:           # 大宋战胜：对方赔款割地给宋
        other["treasury"] -= indemnity
        song["treasury"] += indemnity
        winner, loser = "song", faction_key

    other["relation"] = min(100, max(-100, other.get("relation", 0) + 25))
    other["at_war"] = 0                                  # 息兵罢战
    side = "宋" if not song_pays else faction_key
    other["note"] = (f"与{'宋' if not song_pays else '敌'}议和：割地{round(cede_fraction*100)}%、"
                     f"赔款{round(indemnity)}万贯，息兵罢战。")
    st.write_states(turn, {"song": song, faction_key: other})

    moved = cede_territory(loser, winner, cede_fraction) if cede_fraction > 0 else 0.0
    return {"ok": True, "indemnity": round(indemnity), "cede_fraction": cede_fraction,
            "area_moved": moved, "winner": winner, "loser": loser}
