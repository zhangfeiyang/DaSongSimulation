"""Deterministic monthly economy & military simulation, run for EVERY faction.

This is the "physics" of the world, computed by formula (not the LLM):
  · 国库收支 = 税收(经济) − 军费(兵力×武器) − 行政(人口)   —— 让国库消耗有据可依
  · 军力 = 兵力 × 武器系数(科技) × 民族战力           —— 军力由兵力与科技量化得出
  · 破产(国库<0) → 军队哗变、民生凋敝、政局动荡          —— 适用于所有势力(含敌国)

The LLM/policies only add deltas (shocks, policy coeffs) on top of this baseline.
"""
from __future__ import annotations

from game.seed_data import FACTIONS


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))

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
    """对所有势力施加每年自然演化、经济结算、军力重算与破产惩罚。
    返回玩家(宋)的收支明细 + 破产势力列表，供界面展示。"""
    bankrupts: list[str] = []
    player_budget = {}
    for key, s in states.items():
        _natural_dynamics(s)        # 人口增长、经济向潜力靠拢、政局民生缓慢愈合

        b = budget(s)
        s["treasury"] = round(s["treasury"] + b["net"], 1)
        if key == player_key:
            player_budget = b

        # 破产：入不敷出、国库见底 → 连锁恶果(敌我一视同仁)。
        # 不再直接砍经济(经济由自然演化处理，避免税基归零的死亡螺旋)。
        if s["treasury"] <= BANKRUPT:
            s["stability"] = max(0.0, s["stability"] - 2)
            s["welfare"] = max(0.0, s["welfare"] - 2)
            s["army"] = max(0.0, s["army"] - max(1.0, s["army"] * 0.05))  # 欠饷哗变/逃亡
            bankrupts.append(s.get("name", key))

        # 军力由兵力×科技×民族战力 量化得出(覆盖任何直接赋值)
        s["military"] = expected_military(key, s)

    return {"player_budget": player_budget, "bankrupts": bankrupts}


def _natural_dynamics(s: dict) -> None:
    """各势力每年的自然演化（在政策/事件之外的"国力呼吸"）：
    - 人口：随民生、政局缓慢增长；破产/饥荒则减少。
    - 经济：向由人口与科技决定的"发展潜力"靠拢；政局越稳越快（设下限，使崩溃的经济能复苏）。
    - 政局/民生：向中位 50 缓慢回归——既愈合一时的冲击，也侵蚀疏于经营的高位。"""
    bankrupt = s["treasury"] <= BANKRUPT
    w, st = s["welfare"], s["stability"]

    g = 0.004 * (w / 60.0) * (st / 60.0) - (0.012 if bankrupt else 0.0)
    s["population"] = max(5.0, round(s["population"] * (1 + _clamp(g, -0.03, 0.012)), 1))

    potential = (s["population"] ** 0.5) * (0.6 + 0.012 * s["tech"])
    rate = 0.045 * (0.3 + 0.7 * st / 60.0)          # 政局越稳越快，但保留 30% 下限以脱困
    s["economy"] = max(0.0, round(s["economy"] + (potential - s["economy"]) * _clamp(rate, 0, 0.06), 2))

    heal = 0.03 if not bankrupt else 0.01
    s["stability"] = round(st + (50 - st) * heal, 2)
    s["welfare"] = round(w + (50 - w) * heal, 2)
