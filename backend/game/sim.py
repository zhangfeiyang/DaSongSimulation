"""Deterministic monthly economy & military simulation, run for EVERY faction.

This is the "physics" of the world, computed by formula (not the LLM):
  · 国库收支 = 税收(经济) − 军费(兵力×武器) − 行政(人口)   —— 让国库消耗有据可依
  · 军力 = 兵力 × 武器系数(科技) × 民族战力           —— 军力由兵力与科技量化得出
  · 破产(国库<0) → 军队哗变、民生凋敝、政局动荡          —— 适用于所有势力(含敌国)

The LLM/policies only add deltas (shocks, policy coeffs) on top of this baseline.
"""
from __future__ import annotations

from game.seed_data import FACTIONS

# ---- 经济参数(一回合=一年；校准使北宋开局年年有结余) ----
TAX_K = 60.0       # 年税收 = 经济指数 × TAX_K   (万贯/年)  宋经济100→约6000万贯/年
UPKEEP_K = 30.0    # 年军费 = 兵力 × UPKEEP_K × 武器系数
ADMIN_K = 0.14     # 年行政/百官俸禄 = 人口(万) × ADMIN_K
BANKRUPT = 0.0     # 国库 ≤ 此值视为破产


def weapon_factor(tech: float) -> float:
    """武器系数：科技越高，单位战力越强、也越费钱。范围约 0.55~1.0。"""
    return 0.55 + 0.45 * max(0.0, min(100.0, tech)) / 100.0


# 各势力的"民族战力"系数：由开局数据反推，封存其骑射/martial 传统，
# 使开局军力与设定一致，之后军力随兵力/科技变化而联动。
def _mil_quality() -> dict[str, float]:
    q = {}
    for f in FACTIONS:
        s = f["stats"]
        base = max(0.1, s["army"] * weapon_factor(s["tech"]))
        q[f["key"]] = round(s["military"] / base, 3)
    return q


QUALITY = _mil_quality()


def budget(s: dict) -> dict:
    """某势力本月的收支明细(万贯)。"""
    income = s["economy"] * TAX_K
    upkeep = s["army"] * UPKEEP_K * weapon_factor(s["tech"])
    admin = s["population"] * ADMIN_K
    net = income - upkeep - admin
    return {"income": round(income, 1), "upkeep": round(upkeep, 1),
            "admin": round(admin, 1), "net": round(net, 1)}


def expected_military(key: str, s: dict) -> float:
    q = QUALITY.get(key, 0.6)
    return round(max(0.0, s["army"]) * weapon_factor(s["tech"]) * q, 1)


def apply_monthly(states: dict[str, dict], player_key: str) -> dict:
    """对所有势力施加每月经济结算、军力重算与破产惩罚。
    返回玩家(宋)的收支明细 + 破产势力列表，供界面展示。"""
    bankrupts: list[str] = []
    player_budget = {}
    for key, s in states.items():
        b = budget(s)
        s["treasury"] = round(s["treasury"] + b["net"], 1)
        if key == player_key:
            player_budget = b

        # 破产：入不敷出、国库见底 → 连锁恶果(敌我一视同仁)
        if s["treasury"] <= BANKRUPT:
            s["stability"] = max(0.0, s["stability"] - 4)
            s["welfare"] = max(0.0, s["welfare"] - 2)
            s["economy"] = max(0.0, s["economy"] - 1)
            s["army"] = max(0.0, s["army"] - max(1.0, s["army"] * 0.05))  # 欠饷哗变/逃亡
            bankrupts.append(s.get("name", key))

        # 军力由兵力×科技×民族战力 量化得出(覆盖任何直接赋值)
        s["military"] = expected_military(key, s)

    return {"player_budget": player_budget, "bankrupts": bankrupts}
