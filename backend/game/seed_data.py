"""Historical seed data for the 1068 CE (北宋 熙宁元年) world.

Numbers are illustrative proxies, not exact figures:
  treasury  国库   万贯
  population 人口   万人
  economy   经济指数 (宋=100 基准)
  military  军力指数
  army      常备兵力 万人
  tech      科技 0-100
  stability 政治稳定 0-100
  welfare   民生 0-100
  relation  与玩家(宋)外交 -100..100   (宋自身=100)
"""
from __future__ import annotations

# key, name, name_en, color, is_player, capital(lat,lng), info, stats{...}
FACTIONS = [
    {
        "key": "song", "name": "北宋", "name_en": "Song", "color": "#c0392b",
        "is_player": True, "capital": "34.80,114.30", "info": "天下首富，文教昌盛，然北有强敌、冗官冗兵，财政承压。",
        "stats": dict(treasury=6000, population=11000, economy=100, military=55,
                      army=120, tech=85, stability=62, welfare=65, relation=100),
    },
    {
        "key": "liao", "name": "辽", "name_en": "Liao (Khitan)", "color": "#2c3e50",
        "is_player": False, "capital": "43.96,119.00", "info": "契丹强邦，骑兵冠绝，与宋有澶渊之盟岁币之约。",
        "stats": dict(treasury=1800, population=900, economy=28, military=80,
                      army=60, tech=50, stability=66, welfare=50, relation=10),
    },
    {
        "key": "xixia", "name": "西夏", "name_en": "Western Xia", "color": "#d35400",
        "is_player": False, "capital": "38.50,106.20", "info": "党项立国于河西，控扼丝路，时与宋战和不定。",
        "stats": dict(treasury=400, population=300, economy=12, military=58,
                      army=35, tech=45, stability=55, welfare=42, relation=-30),
    },
    {
        "key": "dali", "name": "大理", "name_en": "Dali", "color": "#16a085",
        "is_player": False, "capital": "25.60,100.27", "info": "西南佛国，物产丰饶，与宋多行茶马互市。",
        "stats": dict(treasury=300, population=200, economy=10, military=30,
                      army=12, tech=42, stability=68, welfare=58, relation=40),
    },
    {
        "key": "tubo", "name": "吐蕃诸部", "name_en": "Tibetan Tribes", "color": "#8e44ad",
        "is_player": False, "capital": "36.10,102.00", "info": "高原诸部林立，青唐唃厮啰一系亲宋抗夏。",
        "stats": dict(treasury=120, population=150, economy=6, military=35,
                      army=18, tech=30, stability=45, welfare=40, relation=25),
    },
    {
        "key": "goryeo", "name": "高丽", "name_en": "Goryeo", "color": "#27ae60",
        "is_player": False, "capital": "37.97,126.55", "info": "海东文邦，慕华向宋，亦周旋于辽之间。",
        "stats": dict(treasury=350, population=250, economy=14, military=33,
                      army=20, tech=55, stability=64, welfare=55, relation=55),
    },
    {
        "key": "daiviet", "name": "大越(李朝)", "name_en": "Dai Viet", "color": "#2980b9",
        "is_player": False, "capital": "21.03,105.85", "info": "交趾李朝，南疆新锐，时扰宋之邕钦。",
        "stats": dict(treasury=180, population=180, economy=8, military=38,
                      army=15, tech=38, stability=60, welfare=52, relation=-10),
    },
    {
        "key": "japan", "name": "日本(平安)", "name_en": "Heian Japan", "color": "#e84393",
        "is_player": False, "capital": "34.99,135.77", "info": "平安朝藤原氏摄关之世，与宋通商贸易往来。",
        "stats": dict(treasury=400, population=600, economy=16, military=28,
                      army=10, tech=50, stability=58, welfare=54, relation=30),
    },
    {
        "key": "karakhanid", "name": "喀喇汗", "name_en": "Kara-Khanid", "color": "#f39c12",
        "is_player": False, "capital": "39.47,75.99", "info": "中亚突厥伊斯兰汗国，扼丝路西段。",
        "stats": dict(treasury=300, population=200, economy=9, military=45,
                      army=22, tech=44, stability=50, welfare=46, relation=0),
    },
    {
        "key": "seljuk", "name": "塞尔柱", "name_en": "Seljuk Empire", "color": "#7f8c8d",
        "is_player": False, "capital": "35.69,51.42", "info": "新兴突厥大帝国，方威震西亚，近年将败拜占庭于曼齐刻尔特。",
        "stats": dict(treasury=900, population=700, economy=22, military=78,
                      army=50, tech=52, stability=60, welfare=48, relation=0),
    },
    {
        "key": "byzantine", "name": "拜占庭", "name_en": "Byzantine Empire", "color": "#9b59b6",
        "is_player": False, "capital": "41.01,28.98", "info": "东罗马，千年古国，正面临塞尔柱东侵之危。",
        "stats": dict(treasury=1100, population=1000, economy=30, military=60,
                      army=40, tech=60, stability=48, welfare=52, relation=5),
    },
    {
        "key": "fatimid", "name": "法蒂玛", "name_en": "Fatimid Caliphate", "color": "#1abc9c",
        "is_player": False, "capital": "30.04,31.24", "info": "什叶派哈里发国，据埃及富庶之地，控红海商路。",
        "stats": dict(treasury=1000, population=500, economy=24, military=50,
                      army=30, tech=58, stability=45, welfare=50, relation=0),
    },
    {
        "key": "hre", "name": "神圣罗马", "name_en": "Holy Roman Empire", "color": "#34495e",
        "is_player": False, "capital": "50.11,8.68", "info": "中欧封建帝国，诸侯林立，正酝酿叙任权之争。",
        "stats": dict(treasury=600, population=800, economy=20, military=55,
                      army=35, tech=45, stability=42, welfare=44, relation=0),
    },
    {
        "key": "chola", "name": "注辇(朱罗)", "name_en": "Chola Empire", "color": "#e67e22",
        "is_player": False, "capital": "10.77,79.13", "info": "南印度海上强权，水师纵横孟加拉湾，曾遣使于宋。",
        "stats": dict(treasury=700, population=900, economy=21, military=52,
                      army=28, tech=50, stability=58, welfare=50, relation=15),
    },
    {
        "key": "ghaznavid", "name": "伽色尼", "name_en": "Ghaznavid", "color": "#95a5a6",
        "is_player": False, "capital": "33.55,68.42", "info": "突厥裔王朝，盛极而衰，西受塞尔柱之逼。",
        "stats": dict(treasury=250, population=300, economy=10, military=40,
                      army=18, tech=42, stability=44, welfare=42, relation=0),
    },
    {
        "key": "kievanrus", "name": "基辅罗斯", "name_en": "Kievan Rus", "color": "#3498db",
        "is_player": False, "capital": "50.45,30.52", "info": "东欧罗斯诸公国，皮毛蜜蜡之利，雅罗斯拉夫诸子分立。",
        "stats": dict(treasury=300, population=500, economy=12, military=42,
                      army=22, tech=38, stability=46, welfare=44, relation=0),
    },
    # ---- 美洲 · 非洲 · 大洋洲（与宋远隔重洋，开局互不知闻，relation=0）----
    {
        "key": "toltec", "name": "托尔特克", "name_en": "Toltec", "color": "#a0522d",
        "is_player": False, "capital": "20.06,-99.34", "info": "中美洲霸主，都于图拉，羽蛇神信仰远播，工艺精巧。",
        "stats": dict(treasury=200, population=250, economy=8, military=30,
                      army=8, tech=35, stability=50, welfare=48, relation=0),
    },
    {
        "key": "mississippi", "name": "密西西比诸部", "name_en": "Mississippian", "color": "#7d6608",
        "is_player": False, "capital": "38.66,-90.06", "info": "北美原住民，卡霍基亚土丘巨城方兴，玉米农耕养众。",
        "stats": dict(treasury=80, population=120, economy=5, military=22,
                      army=5, tech=25, stability=52, welfare=50, relation=0),
    },
    {
        "key": "chimu", "name": "奇穆", "name_en": "Chimú", "color": "#b9770e",
        "is_player": False, "capital": "-8.11,-79.07", "info": "南美安第斯海岸王国，都于昌昌泥城，灌溉与冶金著称。",
        "stats": dict(treasury=180, population=150, economy=7, military=28,
                      army=7, tech=33, stability=54, welfare=50, relation=0),
    },
    {
        "key": "ghana", "name": "加纳帝国", "name_en": "Ghana Empire", "color": "#d4ac0d",
        "is_player": False, "capital": "15.77,-7.98", "info": "西非黄金之国，控撒哈拉商道，黄金食盐贸易甲于一方。",
        "stats": dict(treasury=520, population=200, economy=11, military=38,
                      army=15, tech=38, stability=56, welfare=50, relation=0),
    },
    {
        "key": "ethiopia", "name": "阿比西尼亚", "name_en": "Zagwe (Abyssinia)", "color": "#5d6d1e",
        "is_player": False, "capital": "12.03,39.04", "info": "东非高原基督教王国，扎格维一系，凿石为教堂。",
        "stats": dict(treasury=220, population=200, economy=8, military=35,
                      army=12, tech=40, stability=50, welfare=46, relation=0),
    },
    {
        "key": "mapungubwe", "name": "马蓬古布韦", "name_en": "Mapungubwe", "color": "#784212",
        "is_player": False, "capital": "-22.19,29.39", "info": "南部非洲金石之邦，象牙黄金外贸渐兴，班图诸族汇聚。",
        "stats": dict(treasury=250, population=100, economy=6, military=24,
                      army=6, tech=30, stability=55, welfare=50, relation=0),
    },
    {
        "key": "aborigine", "name": "澳洲原住民", "name_en": "Aboriginal Australians", "color": "#cb4335",
        "is_player": False, "capital": "-25.0,134.0", "info": "南方大陆原住诸族，逐水草而居，岩画歌谣传承万载。",
        "stats": dict(treasury=10, population=50, economy=2, military=12,
                      army=3, tech=12, stability=60, welfare=52, relation=0),
    },
]

# Rough territory polygons (lng, lat). Approximate highlight overlays, not exact borders.
TERRITORIES = {
    "song":       [[104,40],[118,41],[122,34],[121,28],[112,21],[104,23],[103,30]],
    "liao":       [[110,41],[110,48],[126,51],[131,46],[124,41],[116,40]],
    "xixia":      [[99,41],[107,42],[110,39],[107,36],[100,37]],
    "dali":       [[97,28],[103,28],[106,25],[103,22],[98,23]],
    "tubo":       [[78,37],[100,37],[101,31],[88,28],[78,30]],
    "goryeo":     [[124,43],[130,42],[129,35],[126,34],[124,38]],
    "daiviet":    [[102,23],[108,22],[108,18],[104,17],[102,19]],
    "japan":      [[130,32],[136,35],[142,40],[141,42],[134,34],[131,31]],
    "karakhanid": [[68,45],[80,45],[82,40],[74,38],[66,40]],
    "seljuk":     [[45,40],[63,40],[66,33],[55,29],[46,33]],
    "byzantine":  [[22,42],[40,42],[37,36],[26,36],[21,39]],
    "fatimid":    [[25,32],[35,32],[40,24],[33,22],[25,25]],
    "hre":        [[6,54],[18,54],[17,46],[8,46],[5,49]],
    "chola":      [[76,16],[82,15],[81,8],[77,8],[75,11]],
    "ghaznavid":  [[60,36],[72,36],[73,29],[63,28],[59,31]],
    "kievanrus":  [[28,56],[42,55],[40,48],[30,48],[27,52]],
    "toltec":     [[-104,22],[-97,22],[-90,18],[-98,15],[-105,18]],
    "mississippi":[[-95,42],[-82,42],[-81,32],[-92,30],[-96,36]],
    "chimu":      [[-81,-5],[-77,-6],[-70,-14],[-76,-16],[-81,-9]],
    "ghana":      [[-12,18],[-4,18],[-2,13],[-10,11],[-15,15]],
    "ethiopia":   [[36,15],[42,15],[44,8],[37,6],[34,11]],
    "mapungubwe": [[26,-20],[33,-22],[32,-30],[24,-30],[20,-25]],
    "aborigine":  [[114,-22],[135,-12],[150,-25],[145,-38],[120,-33]],
}


# 开局(1068年)各势力「此刻正在发生什么」，作为初始近况；之后随推演逐回合更新。
NOTES = {
    "song": "神宗新即位，锐意求治，朝野方议变法，三冗之弊亟待纾解。",
    "liao": "道宗在位，崇佛奢靡、政渐松弛，然与宋盟好，岁币安享太平。",
    "xixia": "毅宗谅祚新丧、幼主秉常继立，母党梁氏专权，国中暗流涌动。",
    "dali": "段氏奉佛安守，与宋行茶马互市，西南一隅承平。",
    "tubo": "唃厮啰一系据青唐，联宋以抗西夏，诸部仍各自为政。",
    "goryeo": "文宗在位，崇文兴佛、国势鼎盛，频遣使浮海通宋。",
    "daiviet": "李朝圣宗当国，国力上升，南拓占城而北窥宋之邕钦。",
    "japan": "后冷泉朝末，藤原赖通秉摄关之政，庄园林立，院政将兴。",
    "karakhanid": "东西两汗分立、附于塞尔柱，丝路商旅往来不绝。",
    "seljuk": "雄主阿尔普·阿尔斯兰在位，方东征西讨，国势如日中天。",
    "byzantine": "杜卡斯王朝内争、边备废弛，东境塞尔柱压境，危机四伏。",
    "fatimid": "哈里发穆斯坦绥尔在位，逢连年饥荒与军阀混战，国势中衰。",
    "hre": "亨利四世年少亲政，诸侯跋扈，与罗马教廷龃龉渐生。",
    "chola": "毗罗罗阇祚德拉当国，海舶繁盛，称雄于南印度。",
    "ghaznavid": "易卜拉欣在位，与塞尔柱议和，转向印度经营，偏安一隅。",
    "kievanrus": "雅罗斯拉夫诸子分领地而治，兄弟渐生嫌隙，草原游牧寇边。",
    "toltec": "图拉称霸中美，羽蛇神祭祀盛行，然内部党争隐现。",
    "mississippi": "卡霍基亚土丘巨城正值鼎盛，万民辐辏，玉米丰积。",
    "chimu": "昌昌泥城初兴，拓灌溉、并邻部，渐霸太平洋北海岸。",
    "ghana": "黄金食盐贸易鼎盛，然北方阿尔摩拉维德势力渐成大患。",
    "ethiopia": "扎格维王朝立基高原，凿整石以筑教堂，承阿克苏姆余绪。",
    "mapungubwe": "林波波河畔聚落初兴，借印度洋黄金象牙之贸渐富。",
    "aborigine": "诸氏族循「歌之路」而居，承万古「梦创」传统，与世隔绝。",
}


def build_factions_geojson() -> dict:
    by_key = {f["key"]: f for f in FACTIONS}
    feats = []
    for key, coords in TERRITORIES.items():
        f = by_key[key]
        ring = coords + [coords[0]]  # close the ring
        feats.append({
            "type": "Feature",
            "properties": {"key": key, "name": f["name"], "color": f["color"],
                           "is_player": f["is_player"]},
            "geometry": {"type": "Polygon", "coordinates": [ring]},
        })
    return {"type": "FeatureCollection", "features": feats}
