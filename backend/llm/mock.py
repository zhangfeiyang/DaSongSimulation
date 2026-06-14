"""Offline deterministic推演 used when provider == "mock" (no API key needed).

Keyword heuristics on the policy text produce plausible deltas so the whole game
loop (UI, DB, map) can be played and demoed without any LLM. Produces both a
文言 narrative and a 白话 (plain modern Chinese) translation.
"""
from __future__ import annotations

import json
import random
import re


# pattern -> (宋 stat deltas, 文言 fragment, 白话 fragment)
RULES = [
    (r"减税|轻徭|薄赋|免税|赈|济贫|惠民",
     {"welfare": 4, "stability": 3, "treasury": -250, "economy": 1.5},
     "蠲免赋税、赈济黎庶，民心稍安，然国库为之一空。",
     "减免赋税、救济百姓，民心安定了一些，但国库也因此空虚了不少。"),
    (r"变法|新法|改革|青苗|募役|方田|均输|王安石",
     {"economy": 2.5, "treasury": 200, "stability": -4, "welfare": -1},
     "新法次第推行，府库渐充，然旧党哗然、闾里扰动，执行多有走样。",
     "新法逐步推行，国库渐渐充实，但保守派强烈反对、民间也有骚动，执行中走了样。"),
    (r"募兵|扩军|练兵|养兵|增兵|强军",
     {"military": 4, "army": 6, "treasury": -300, "stability": -1},
     "招募新军、勤加操练，军容稍振，然糜费日增，冗兵之弊隐现。",
     "招募并操练新军，军队面貌有所改善，但开销大增，养兵过多的弊病开始显现。"),
    (r"水利|治河|修渠|漕运|垦田|农桑|劝农",
     {"economy": 2, "welfare": 3, "treasury": -150, "population": 20},
     "兴修水利、劝课农桑，岁稔可期，仓廪渐实。",
     "兴修水利、鼓励农耕，今年有望丰收，粮仓渐渐充实。"),
    (r"兴学|科举|文教|书院|印书|学校|崇儒",
     {"tech": 2.5, "stability": 2, "treasury": -120},
     "广设学校、增贡举之额，文教益盛，士心归附。",
     "广办学校、增加科举名额，文化教育更兴盛，读书人也更归心。"),
    (r"通商|互市|海贸|市舶|茶马|丝路|贸易",
     {"economy": 3, "treasury": 300, "tech": 1},
     "广开市舶、通商四夷，舶来之利充盈府库。",
     "扩大海外通商、与各国互市，贸易收入让国库充盈起来。"),
    (r"伐夏|攻夏|西征|讨夏|河湟",
     {"military": 2, "army": -4, "treasury": -400, "stability": -3},
     "兴师西向，战事胶着，士马疲于河陇，府帑为之耗竭。",
     "出兵西征西夏，战事陷入僵持，军队在西北疲于奔命，国库被大量消耗。"),
    (r"和辽|岁币|结好|盟好|睦邻|怀柔|聘辽|修好|澶渊|遣使",
     {"stability": 2, "treasury": -120, "military": -1},
     "遣使修好、岁输缯帛，北鄙暂安，边民得以休息。",
     "派使者与辽国修好、每年送些财帛，北方边境暂时安定，边民得以休养。"),
    (r"反腐|肃贪|考课|整顿吏治|裁冗",
     {"stability": 3, "treasury": 150, "welfare": 1},
     "澄清吏治、裁汰冗滥，纲纪稍肃，然触怒权要。",
     "整顿官场、裁撤多余官员，纪律有所好转，但也得罪了权贵。"),
]

REACT_FACTIONS = {  # policy keyword -> faction key -> relation delta
    r"伐夏|攻夏|讨夏": {"xixia": -20, "liao": -5},
    r"和辽|岁币|结好|聘辽|修好|澶渊": {"liao": 12},
    r"通商|互市|海贸|市舶": {"dali": 5, "goryeo": 5, "japan": 4, "chola": 3},
    r"高丽": {"goryeo": 8},
}

REACT_NOTES = {  # policy keyword -> faction key -> 近况
    r"伐夏|攻夏|讨夏": {
        "xixia": "宋军压境，朝野震恐，梁氏急调蕃骑屯守横山以御之。",
        "liao": "宋夏交兵，辽廷坐观成败，密遣使两端斡旋以渔其利。"},
    r"和辽|岁币|结好|聘辽|修好|澶渊": {
        "liao": "宋使奉币来聘，辽主大悦，许开榷场互市，北鄙益安。"},
    r"通商|互市|海贸|市舶": {
        "dali": "宋广市舶，大理茶马商道转盛，段氏获利。",
        "goryeo": "宋商舶频至，高丽求购典籍药材愈殷。",
        "japan": "宋钱涌入，博多商港愈见喧阗。",
        "chola": "南海商路畅通，注辇番舶愿赴广州贸易。"},
    r"高丽": {"goryeo": "宋廷垂顾，高丽君臣感佩，益思亲附。"},
}

# (文言 narrative phrasing, delta, 白话 event caption)
RANDOM_EVENTS = [
    ("黄河汛涨，京东路州县罹灾，流民载道。", {"welfare": -3, "stability": -2, "treasury": -120},
     "黄河泛滥，京东一带受灾，灾民流离失所。"),
    ("江南大稔，米价低平，市井称庆。", {"welfare": 3, "economy": 1.5, "treasury": 100},
     "江南大丰收，米价低廉，市井百姓欢庆。"),
    ("辽遣使来贺，馆于都亭驿，邦交粗安。", {"stability": 1},
     "辽国派使者前来祝贺，两国邦交大体平稳。"),
    ("西夏游骑寇边，掠去人畜，边将告急。", {"military": -1, "stability": -1, "army": -2},
     "西夏骑兵侵扰边境、掳掠人畜，边将告急。"),
    ("彗星见于东方，朝野讹言，人心浮动。", {"stability": -2},
     "东方出现彗星，朝野谣言四起，人心浮动。"),
    ("市舶司岁入逾额，泉广番舶云集。", {"treasury": 150, "economy": 1},
     "市舶司收入超额，泉州、广州外国商船云集。"),
]

# 具有"延迟回报 / 持续走高"特性的国策：用 {init, steady} 表示先投入后回报、先小后大；
# half_life 为成熟半衰期(月)，越大越"大后期"。
PROFILE_COEFFS = {
    # 一回合=一年：国库系数为"每年"，half_life 单位为"年"
    r"市舶|口岸|海贸|通商|互市|丝路|贸易":
        ({"treasury": {"init": 240, "steady": 1360}, "economy": {"init": 0.5, "steady": 2.0}}, 4),
    r"兴学|科举|文教|书院|学校|崇儒|格物|研发|科技|工巧|军器|火器|匠|水利|运河|垦|远洋":
        ({"treasury": {"init": -960, "steady": 320}, "tech": {"init": 0.6, "steady": 2.5},
          "science": {"init": 6, "steady": 24}}, 18),
}

OPTION_POOL = [
    {"title": "推行青苗法", "desc": "春贷钱谷于民，秋收加息偿还，以抑兼并、增国用。"},
    {"title": "整饬河防", "desc": "征夫治理黄河，防秋汛之患，安京畿之民。"},
    {"title": "开拓市舶", "desc": "增设市舶司，招徕番商，广海贸之利。"},
    {"title": "经略河湟", "desc": "招抚吐蕃诸部，断西夏右臂，徐图灵武。"},
    {"title": "裁汰冗官", "desc": "核实员额，澄清选格，省靡费而肃纲纪。"},
    {"title": "广兴学校", "desc": "州县立学，增贡举额，作育人才。"},
    {"title": "遣使聘辽", "desc": "修澶渊之好，议岁币与榷场，纾北顾之忧。"},
]


def _extract_policy(user: str) -> str:
    m = re.search(r"颁布的政策】\s*(.+?)\s*请据此推演", user, re.S)
    return m.group(1).strip() if m else ""


def _derive_title(policy: str) -> str:
    seg = re.split(r"[，。；、\n]", policy.strip(), 1)[0].strip()
    return seg[:16] if seg else ""


def _extract_turn(user: str) -> int:
    m = re.search(r"第(\d+)回合", user)
    return int(m.group(1)) if m else 1


def mock_complete(system: str, user: str) -> str:
    policy = _extract_policy(user)
    turn = _extract_turn(user)
    rng = random.Random(hash((policy, turn)) & 0xFFFFFFFF)

    song = {"treasury": 0.0, "economy": 0.0, "military": 0.0, "army": 0.0,
            "tech": 0.0, "stability": 0.0, "welfare": 0.0, "population": 0.0}
    frags, frags_plain, events = [], [], []

    # 本年新政的即时影响，并据匹配规则推出其"持续影响系数"(引擎逐年衰减累计)。
    # 一回合=一年：国库类数值按年放大(×8)。
    TSCALE = 8.0
    matched = False
    coeff_acc: dict[str, float] = {}
    for pat, deltas, frag, frag_plain in RULES:
        if re.search(pat, policy):
            matched = True
            for k, v in deltas.items():
                mult = TSCALE if k == "treasury" else 1.0
                song[k] += v * mult * (0.8 + rng.random() * 0.5)
                coeff_acc[k] = coeff_acc.get(k, 0.0) + v * mult * 0.4
            frags.append(frag)
            frags_plain.append(frag_plain)

    # 延迟回报 / 持续走高型国策：用 {init, steady} 覆盖相关项的系数；half_life(年) 取较大值(大后期)
    half_life = 2   # 默认速效渐衰(年)
    for pat, (prof, hl) in PROFILE_COEFFS.items():
        if re.search(pat, policy):
            matched = True
            half_life = max(half_life, hl)
            for k, spec in prof.items():
                coeff_acc[k] = dict(spec)
    if not matched:
        song["economy"] += 0.5
        song["treasury"] += 480
        frags.append("皇帝萧规曹随，朝局平稳，府库循常岁入。")
        frags_plain.append("皇帝沿用旧制、没有新政，朝局平稳，国库照常进项。")

    changes: dict[str, dict] = {}
    for pat, react in REACT_FACTIONS.items():
        if re.search(pat, policy):
            for fk, rv in react.items():
                changes.setdefault(fk, {})["relation"] = changes.get(fk, {}).get("relation", 0) + rv
            for fk, note in REACT_NOTES.get(pat, {}).items():
                changes.setdefault(fk, {})["note"] = note

    ev_classic = ""
    if rng.random() < 0.85:
        ev_classic, ev_delta, ev_plain = rng.choice(RANDOM_EVENTS)
        events.append(ev_plain)
        for k, v in ev_delta.items():
            song[k] = song.get(k, 0) + (v * 8.0 if k == "treasury" else v)

    song["note"] = "；".join(frags)[:120]
    changes["song"] = {k: round(v, 1) for k, v in song.items() if k != "note"}
    changes["song"]["note"] = song["note"]

    options = rng.sample(OPTION_POOL, 3)
    narrative = "熙宁纪事：" + "；".join(frags) + (f" 是岁，{ev_classic}" if ev_classic else "")
    narrative_plain = "本年纪事：" + "；".join(frags_plain) + (f" 这一年，{events[0]}" if events else "")

    # 把本月有实质内容的新政确立为长期国策，并附其持续影响系数与衰减
    new_policies = []
    if matched:
        title = _derive_title(policy)
        if title:
            coeffs_out = {}
            for k, v in coeff_acc.items():
                if isinstance(v, dict):
                    coeffs_out[k] = {kk: round(vv, 1) for kk, vv in v.items()}
                elif abs(v) >= 0.05:
                    coeffs_out[k] = round(v, 1)
            new_policies.append({"title": title, "summary": policy[:60],
                                 "coeffs": coeffs_out, "half_life": half_life})

    out = {
        "narrative": narrative,
        "narrative_plain": narrative_plain,
        "events": events,
        "changes": changes,
        "options": options,
        "policy_updates": {"new_policies": new_policies, "ended_policies": []},
        "difficulty": "（离线推演）政策执行受财政与吏治掣肘，效果存在不确定性。",
        "verdict": "局势在可控范围内演进。" if matched else "无为而治，平稳过渡。",
    }
    return json.dumps(out, ensure_ascii=False)
