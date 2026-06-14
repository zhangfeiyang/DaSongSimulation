"""列国自主异动（不经过 LLM 的"世界自有其势"）：
- 外交关系逐年向各势力的"天然立场"回归：一次性的赏赐/结好会淡去，世仇仍是世仇。
- 与大宋接壤的敌对强邻，每年有概率寇边劫掠，使外交与边防成为玩家必须经营之事。
"""
from __future__ import annotations

import random

from game.seed_data import FACTIONS

# 各势力开局对宋的"天然立场"——关系逐年向它回归
SEED_RELATION = {f["key"]: f["stats"]["relation"] for f in FACTIONS}

# 能寇大宋边境的接壤强邻（远隔重洋者不在此列）
NEIGHBORS = {"xixia", "liao", "tubo", "dali", "daiviet", "goryeo", "karakhanid"}

RAID_BORDERS = {
    "xixia": "鄜延、环庆", "liao": "河北、河东", "tubo": "熙河", "dali": "梓夔",
    "daiviet": "邕、钦", "goryeo": "登莱", "karakhanid": "西州",
}


def world_react(states: dict[str, dict], player_key: str = "song") -> list[str]:
    """对各势力施加外交回归与边境劫掠，原地修改 states，返回本年世界事件列表。"""
    events: list[str] = []
    rng = random.Random()
    song = states.get(player_key)

    for key, s in states.items():
        if s.get("is_player"):
            continue
        # 外交向天然立场缓慢回归
        base = SEED_RELATION.get(key, 0)
        s["relation"] = round(s["relation"] + (base - s["relation"]) * 0.06, 1)

    if song is None:
        return events

    # 敌对强邻寇边（每年至多两起）
    raids = 0
    for key in NEIGHBORS:
        if raids >= 2:
            break
        s = states.get(key)
        if not s or s["military"] <= 20 or s["relation"] > -25:
            continue
        hostility = (-s["relation"]) / 100.0            # 0.25 ~ 1.0
        # 越敌对、兵越强，寇边越频；激怒强邻(伐夏等)会显著升级劫掠
        chance = min(0.45, 0.40 * hostility * (s["military"] / 45.0))
        if rng.random() < chance:
            raids += 1
            loot = round(rng.uniform(200, 600) * hostility, 1)
            song["treasury"] = round(song["treasury"] - loot, 1)
            song["welfare"] = max(0.0, song["welfare"] - rng.uniform(1, 2))
            song["army"] = max(0.0, round(song["army"] - rng.uniform(1, 3), 1))
            s["treasury"] = round(s["treasury"] + loot * 0.5, 1)        # 劫掠所获
            s["relation"] = max(-100.0, s["relation"] - 3)
            s["note"] = f"纵骑寇宋{RAID_BORDERS.get(key, '边境')}，掠人畜而还。"
            events.append(f"{s['name']}游骑寇{RAID_BORDERS.get(key, '边境')}，"
                          f"掠去人畜、耗宋帑约{round(loot)}万贯，边民流离。")
    return events
