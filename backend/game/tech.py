"""精简科技树（参考文明6，去除远古科技，自宋代工巧起步，终于大模型AI）。

研究机制：每回合按"国力"积累科技点(science)，玩家选定一项可研科技，
积满其 cost 即解锁，并把 effect 永久加成落到大宋国情。tech 状态以 JSON 存于 game_state。
"""
from __future__ import annotations

# id, name, era, cost(科技点), prereqs, effect(完成后对大宋的永久加成), blurb
TECHS = [
    # —— 工巧之世（北宋本代）——
    ("printing", "活字印刷", "工巧之世", 220, [], {"tech": 3, "stability": 3},
     "毕昇活字，文教大兴、政令速达。"),
    ("gunpowder", "火药军械", "工巧之世", 260, [], {"tech": 3, "army": 4},
     "霹雳炮、震天雷，火器登上战阵。"),
    ("compass", "指南航海", "工巧之世", 240, [], {"tech": 3, "economy": 4},
     "罗盘指南，远洋市舶之利大开。"),
    ("seedrice", "占城稻作", "工巧之世", 200, [], {"welfare": 4, "economy": 3},
     "占城早稻，岁可两熟，仓廪渐实。"),
    ("watermill", "水力机械", "工巧之世", 280, ["seedrice"], {"economy": 5, "tech": 2},
     "水转大纺车、水碓，工坊初具规模。"),

    # —— 革新之世 ——
    ("cannon", "铸炮之术", "革新之世", 420, ["gunpowder"], {"army": 6, "tech": 3},
     "铜铁铸炮，攻城野战，威力倍增。"),
    ("oceanchart", "远洋海图", "革新之世", 440, ["compass"], {"economy": 7},
     "海图与牵星术，下西洋、通四海。"),
    ("bank", "钱庄银行", "革新之世", 460, ["watermill"], {"economy": 6, "tech": 2},
     "钱庄汇兑、信用借贷，商业资本勃兴。"),
    ("printpress", "雕版书业", "革新之世", 400, ["printing"], {"tech": 5},
     "书籍广布，知识传播、学术昌明。"),

    # —— 工业之世 ——
    ("steam", "蒸汽机", "工业之世", 720, ["watermill", "bank"], {"economy": 10, "tech": 5},
     "蒸汽为动力，工厂林立，产能跃升。"),
    ("railroad", "铁路", "工业之世", 820, ["steam"], {"economy": 9, "army": 4},
     "钢铁长龙，调兵运货，地无远近。"),
    ("telegraph", "电报", "工业之世", 700, ["printpress"], {"tech": 6, "stability": 4},
     "电讯千里，政令军情瞬息可达。"),
    ("modernarmy", "新式陆军", "工业之世", 780, ["cannon", "railroad"], {"army": 8, "tech": 4},
     "线膛枪炮、近代编制，陆军脱胎换骨。"),

    # —— 现代之世 ——
    ("electricity", "电力", "现代之世", 1100, ["steam", "telegraph"], {"economy": 12, "tech": 8},
     "电气之光，照亮工业与万家。"),
    ("combustion", "内燃机", "现代之世", 1150, ["railroad"], {"economy": 10, "army": 6},
     "汽车飞机之基，机动力空前。"),
    ("medicine", "现代医学", "现代之世", 1000, ["electricity"], {"welfare": 12, "stability": 5},
     "防疫与外科，人口寿数大增。"),

    # —— 信息·智能之世 ——
    ("computer", "电子计算机", "信息·智能之世", 1500, ["electricity", "combustion"],
     {"tech": 12, "economy": 10}, "电子计算，开信息时代之门。"),
    ("internet", "互联网", "信息·智能之世", 1700, ["computer"], {"economy": 14, "tech": 8},
     "环球互联，信息与商贸无远弗届。"),
    ("semiconductor", "半导体", "信息·智能之世", 1800, ["computer"], {"tech": 14, "army": 8},
     "芯片之上，算力即国力。"),
    ("ai_llm", "大模型 AI", "信息·智能之世", 2600, ["internet", "semiconductor"],
     {"tech": 20, "economy": 18, "army": 10, "stability": 6},
     "大语言模型横空出世，通晓古今、辅弼万机，国力为之一新。"),
]

TECH_BY_ID = {t[0]: t for t in TECHS}
ERAS = ["工巧之世", "革新之世", "工业之世", "现代之世", "信息·智能之世"]


def initial_state() -> dict:
    return {"science": 0.0, "current": None, "progress": 0.0, "researched": []}


def policy_science_bonus(active_policies: list[dict]) -> float:
    """现行国策对科技点/月 的额外加成(可正可负)。"""
    return round(sum((p.get("current_effect") or {}).get("science", 0.0)
                     for p in (active_policies or [])), 2)


def base_rate(song: dict | None) -> float:
    """基础科技点速率（随经济与科技水平增长）。

    校准（一回合=一年）：北宋熙宁元年(1068) 距今(约2026) ≈ 958 年 = 958 回合；
    全科技树总成本 ≈ 16790 点；故历史平均 ≈ 16790/958 ≈ 17.5 点/年。
    据此取系数，使开局(经济100、科技85) 基础速率 ≈ 18 点/年——
    不投入则一项科技需十数年，需靠兴学/科研等政策与国力增长来加速。"""
    if not song:
        return 0.0
    return round(song["economy"] * 0.07 + song["tech"] * 0.13, 2)


def science_rate(song: dict | None, bonus: float = 0.0) -> float:
    """实际每月科技点 = 基础速率 + 政策加成(可正可负)，下限 0。"""
    return round(max(0.0, base_rate(song) + (bonus or 0.0)), 1)


def is_available(tid: str, researched: list[str]) -> bool:
    t = TECH_BY_ID.get(tid)
    if not t or tid in researched:
        return False
    return all(p in researched for p in t[4])


def tree_view(ts: dict, song: dict | None, bonus: float = 0.0) -> dict:
    researched = ts.get("researched", [])
    items = []
    for tid, name, era, cost, prereqs, effect, blurb in TECHS:
        if tid in researched:
            status = "done"
        elif is_available(tid, researched):
            status = "available"
        else:
            status = "locked"
        items.append({"id": tid, "name": name, "era": era, "cost": cost,
                      "prereqs": prereqs, "effect": effect, "blurb": blurb,
                      "status": status})
    return {
        "eras": ERAS,
        "techs": items,
        "current": ts.get("current"),
        "progress": round(ts.get("progress", 0.0), 1),
        "science": round(ts.get("science", 0.0), 1),
        "rate": science_rate(song, bonus),
        "base_rate": base_rate(song),
        "policy_bonus": round(bonus or 0.0, 1),
        "researched": researched,
    }


def advance_research(song: dict | None, bonus: float = 0.0) -> dict:
    """每回合推进研究：积累科技点(基础速率 + 政策加成)，完成则把 effect 落到大宋。"""
    from game import state as st
    ts = st.get_tech_state()
    completed = None
    rate = science_rate(song, bonus)
    ts["progress"] = ts.get("progress", 0.0) + rate
    ts["science"] = ts.get("science", 0.0) + rate
    cur = ts.get("current")
    if cur and cur in TECH_BY_ID:
        cost = TECH_BY_ID[cur][3]
        if ts["progress"] >= cost:
            ts["researched"] = ts.get("researched", []) + [cur]
            effect = TECH_BY_ID[cur][5]
            if song is not None:
                for k, v in effect.items():
                    if k in song:
                        song[k] = song[k] + v
            completed = {"id": cur, "name": TECH_BY_ID[cur][1], "effect": effect}
            ts["current"] = None
            ts["progress"] = 0.0
    st.save_tech_state(ts)
    return {"completed": completed, "gain": rate, "bonus": round(bonus or 0.0, 1)}
