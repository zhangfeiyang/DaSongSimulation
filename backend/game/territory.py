"""Generate detailed faction territories by clipping REAL country geometries
from data/world.geojson, with **jagged (犬牙交错) internal borders**.

Peripheral powers reuse whole modern-country outlines (real coastlines = naturally
jagged). Where we must cut a landmass ourselves (e.g. splitting China among
宋/辽/西夏/吐蕃/大理, or trimming a country with a clip box), we replace the
straight box edges with fractal **midpoint-displacement** lines so borders
interlock instead of running dead straight.

Borders stay gap-free because each cut polygon is generated ONCE and reused for
both the faction that owns it and the neighbours that subtract it.

Falls back to the crude polygons in seed_data if shapely is unavailable.
"""
from __future__ import annotations

import json
import random

from config import DATA_DIR
from game.seed_data import FACTIONS, build_factions_geojson as _crude

# Peripheral factions: whole country outlines (+ optional clip box / China slice).
SPEC = {
    "goryeo":     {"countries": ["North Korea", "South Korea"]},
    "daiviet":    {"countries": ["Vietnam"], "clip": (101, 15.5, 112, 24)},
    "japan":      {"countries": ["Japan"], "clip": (128, 30, 146, 46)},
    "karakhanid": {"countries": ["Uzbekistan", "Kyrgyzstan", "Tajikistan", "Turkmenistan"]},
    "seljuk":     {"countries": ["Iran", "Iraq"]},
    "byzantine":  {"countries": ["Greece", "Turkey"]},
    "fatimid":    {"countries": ["Egypt", "Libya"]},
    "hre":        {"countries": ["Germany", "Austria", "Czech Republic", "Switzerland"]},
    "chola":      {"countries": ["India"], "clip": (72, 6, 84, 21)},
    "ghaznavid":  {"countries": ["Afghanistan", "Pakistan"]},
    "kievanrus":  {"countries": ["Ukraine", "Belarus"], "russia_box": (28, 49, 52, 62)},
    # New World / Africa / Oceania — real coastlines, naturally jagged.
    "toltec":     {"countries": ["Mexico", "Guatemala"]},
    "mississippi":{"countries": ["USA"], "clip": (-104, 28, -80, 44)},
    "chimu":      {"countries": ["Peru", "Ecuador"]},
    "ghana":      {"countries": ["Mali", "Mauritania", "Senegal"]},
    "ethiopia":   {"countries": ["Ethiopia", "Eritrea"]},
    "mapungubwe": {"countries": ["Zimbabwe", "South Africa", "Botswana"]},
    "aborigine":  {"countries": ["Australia"]},
}

# China interior slices (minlng, minlat, maxlng, maxlat). Resolved in this order;
# each later faction is cut against the union of earlier boxes (running claim).
CHINA_ORDER = [
    ("dali",       (97, 21, 107, 29)),     # 云南
    ("tubo",       (76, 27, 100, 39)),     # 青藏 / 青海
    ("karakhanid", (73, 37, 92, 47)),      # 塔里木 / 准噶尔 (并入喀喇汗)
    ("xixia",      (100, 35, 113, 42)),    # 河西 / 宁夏 / 河套
    ("liao",       (110, 40, 135, 53)),    # 满洲 (并入辽，另含蒙古)
    ("song",       (100, 20, 124, 42)),    # 其余东部 / 中原 / 江南 (取剩余)
]


def _displace(a, b, rng, amp, depth, out):
    """Recursive midpoint displacement of segment a->b (appends a, not b)."""
    if depth <= 0:
        out.append(a)
        return
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    length = (dx * dx + dy * dy) ** 0.5 or 1.0
    px, py = -dy / length, dx / length            # unit perpendicular
    off = (rng.random() * 2 - 1) * amp
    mid = ((ax + bx) / 2 + px * off, (ay + by) / 2 + py * off)
    _displace(a, mid, rng, amp * 0.6, depth - 1, out)
    _displace(mid, b, rng, amp * 0.6, depth - 1, out)


def _jagged_box(t, amp=0.7, depth=5):
    """A box whose edges are fractal-jagged. Deterministic per-edge (seeded by
    endpoints) so the same edge jitters identically wherever it is reused."""
    from shapely.geometry import Polygon
    minx, miny, maxx, maxy = t
    corners = [(minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy)]
    pts: list = []
    for i in range(4):
        a, b = corners[i], corners[(i + 1) % 4]
        seed = hash((round(a[0], 2), round(a[1], 2), round(b[0], 2), round(b[1], 2))) & 0xFFFFFFFF
        _displace(a, b, random.Random(seed), amp, depth, pts)
    poly = Polygon(pts)
    return poly if poly.is_valid else poly.buffer(0)


def build() -> dict:
    try:
        from shapely.geometry import shape
        from shapely.ops import unary_union
    except Exception:
        return _crude()

    world = json.loads((DATA_DIR / "world.geojson").read_text(encoding="utf-8"))
    geoms = {f["properties"].get("name"): shape(f["geometry"]) for f in world["features"]}
    if "China" not in geoms:
        return _crude()
    by_key = {f["key"]: f for f in FACTIONS}

    def clean(g):
        return g.buffer(0) if (g is not None and not g.is_valid) else g

    china = clean(geoms["China"])

    # --- split China with jagged, running-claim subtraction ---
    china_parts: dict = {}
    claimed = None
    for key, bbox in CHINA_ORDER:
        jb = _jagged_box(bbox)
        part = china.intersection(jb)
        if claimed is not None:
            part = part.difference(claimed)
        china_parts[key] = clean(part)
        claimed = jb if claimed is None else unary_union([claimed, jb])

    result: dict = {
        "song": china_parts["song"], "xixia": china_parts["xixia"],
        "tubo": china_parts["tubo"], "dali": china_parts["dali"],
    }

    # --- peripheral factions ---
    for key, spec in SPEC.items():
        parts = [clean(geoms[c]) for c in spec.get("countries", []) if c in geoms]
        g = unary_union(parts) if parts else None
        if g is not None and "clip" in spec:
            g = g.intersection(_jagged_box(spec["clip"]))
        if "russia_box" in spec and "Russia" in geoms:
            rp = clean(geoms["Russia"]).intersection(_jagged_box(spec["russia_box"]))
            g = unary_union([x for x in (g, rp) if x is not None])
        if key in china_parts:                       # karakhanid / liao also own a China slice
            g = unary_union([x for x in (g, china_parts[key]) if x is not None and not x.is_empty])
        result[key] = g

    # 辽 = 蒙古(整国) + 满洲(China 切片)，不在 SPEC 中，单独拼装
    liao_bits = [china_parts.get("liao")]
    if "Mongolia" in geoms:
        liao_bits.append(clean(geoms["Mongolia"]))
    liao_bits = [x for x in liao_bits if x is not None and not x.is_empty]
    if liao_bits:
        result["liao"] = unary_union(liao_bits)

    from shapely.geometry import mapping
    feats = []
    for key, g in result.items():
        if g is None or g.is_empty:
            continue
        f = by_key[key]
        g = g.simplify(0.05, preserve_topology=True)
        feats.append({
            "type": "Feature",
            "properties": {"key": key, "name": f["name"], "color": f["color"],
                           "is_player": f["is_player"]},
            "geometry": mapping(g),
        })
    return {"type": "FeatureCollection", "features": feats}


def write() -> None:
    (DATA_DIR / "factions.geojson").write_text(
        json.dumps(build(), ensure_ascii=False), encoding="utf-8")
