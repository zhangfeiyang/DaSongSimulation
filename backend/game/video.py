"""Per-turn world snapshots -> evolution video (mp4).

Each turn the DB already holds a full faction_state snapshot, so we render one map
frame per turn (date + territories shaded by 国力 + power leaderboard + that month's
纪事) and stitch them with ffmpeg into a video of the world evolving over time.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPoly
from matplotlib.font_manager import FontProperties

from config import DATA_DIR, START_YEAR, START_MONTH
from game import state as st

FONT_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
FP = FontProperties(fname=FONT_PATH)
FP_BIG = FontProperties(fname=FONT_PATH, size=30)
FP_MID = FontProperties(fname=FONT_PATH, size=15)
FP_SM = FontProperties(fname=FONT_PATH, size=12)

ERAS = [(1068, 1077, "熙宁"), (1078, 1085, "元丰"), (1086, 1093, "元祐"),
        (1094, 1097, "绍圣"), (1098, 1100, "元符"), (1101, 1101, "建中靖国"),
        (1102, 1106, "崇宁"), (1107, 1110, "大观"), (1111, 1118, "政和")]
MONTHS = ["正", "二", "三", "四", "五", "六", "七", "八", "九", "十", "冬", "腊"]


def date_for_turn(t: int) -> tuple[int, int]:
    return START_YEAR + t, START_MONTH          # 一回合 = 一年


def reign_str(y: int, m: int = 1) -> str:
    era = next((e for e in ERAS if e[0] <= y <= e[1]), None)
    if era:
        n = y - era[0] + 1
        return f"{era[2]}{'元' if n == 1 else n}年　（公元{y}年）"
    return f"公元{y}年"


def _rings(geom):
    t, c = geom["type"], geom["coordinates"]
    if t == "Polygon":
        return [c[0]]
    if t == "MultiPolygon":
        return [poly[0] for poly in c]
    return []


def _draw_frame(ax, world_feats, fac_feats, states, date_str, narrative):
    ax.clear()
    ax.set_xlim(-170, 188)
    ax.set_ylim(-58, 84)
    ax.axis("off")
    ax.set_facecolor("#9fc3d6")  # ocean

    for f in world_feats:
        for ring in _rings(f["geometry"]):
            ax.add_patch(MplPoly(ring, closed=True, facecolor="#e9dcc0",
                                 edgecolor="#c9b58a", linewidth=0.3, zorder=1))

    power = {k: s["economy"] * 0.5 + s["military"] * 0.4 + s["tech"] * 0.3
             for k, s in states.items()}
    mx = max(power.values()) if power else 1
    for f in fac_feats:
        key = f["properties"]["key"]
        color = f["properties"]["color"]
        alpha = 0.40 + 0.52 * (power.get(key, 0) / mx) if key in states else 0.40
        for ring in _rings(f["geometry"]):
            ax.add_patch(MplPoly(ring, closed=True, facecolor=color,
                                 edgecolor="white", linewidth=0.5, alpha=alpha, zorder=2))

    dark = dict(boxstyle="round,pad=0.4", facecolor=(0.11, 0.09, 0.08, 0.72), edgecolor="none")
    ax.text(0.012, 0.965, date_str, transform=ax.transAxes, va="top", ha="left",
            color="#ffe9b0", fontproperties=FP_BIG, bbox=dark, zorder=5)

    # power leaderboard (top 8 by economy)
    top = sorted(states.values(), key=lambda s: -s["economy"])[:8]
    lines = ["〔天下国力 · 经济〕"]
    for s in top:
        star = "★" if s.get("is_player") else "  "
        lines.append(f"{star}{s['name']:<6} {round(s['economy']):>3}")
    ax.text(0.985, 0.95, "\n".join(lines), transform=ax.transAxes, va="top", ha="right",
            color="#fff", fontproperties=FP_SM, linespacing=1.5, bbox=dark, zorder=5)

    if narrative:
        wrapped = "\n".join(textwrap.wrap(narrative, width=46)[:3])
        ax.text(0.5, 0.045, wrapped, transform=ax.transAxes, va="bottom", ha="center",
                color="#fff", fontproperties=FP_MID, linespacing=1.5,
                bbox=dict(boxstyle="round,pad=0.6", facecolor=(0.11, 0.09, 0.08, 0.74),
                          edgecolor="#c9a24b"), zorder=5)

    ax.text(0.988, 0.02, "大宋模拟器 · 世界演化", transform=ax.transAxes, va="bottom",
            ha="right", color=(1, 1, 1, 0.6), fontproperties=FP_SM, zorder=5)


def build_video(seconds_per_turn: float = 0.9) -> str:
    gs = st.get_game_state()
    last = gs["turn"]
    world = json.loads((DATA_DIR / "world.geojson").read_text(encoding="utf-8"))["features"]
    facs = json.loads((DATA_DIR / "factions.geojson").read_text(encoding="utf-8"))["features"]
    hist = {h["turn"]: h for h in st.get_history()}

    tmp = tempfile.mkdtemp(prefix="song_frames_")
    fig = plt.figure(figsize=(12.8, 7.2), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    try:
        for t in range(0, last + 1):
            states = st.get_states_at(t)
            y, m = date_for_turn(t)
            h = hist.get(t)
            if h:
                narrative = h.get("narrative_plain") or h.get("narrative") or ""
            else:
                narrative = "世界肇始 · 北宋熙宁元年，天下列国并立。" if t == 0 else ""
            _draw_frame(ax, world, facs, states, reign_str(y, m), narrative)
            fig.savefig(os.path.join(tmp, f"f{t:04d}.png"), dpi=100)
        plt.close(fig)

        out = str(DATA_DIR / "evolution.mp4")
        fps = max(0.2, 1.0 / max(0.1, seconds_per_turn))
        cmd = ["ffmpeg", "-y", "-framerate", f"{fps:.4f}",
               "-i", os.path.join(tmp, "f%04d.png"),
               "-c:v", "libx264", "-pix_fmt", "yuv420p",
               "-vf", "scale=1280:720", "-r", "25", out]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg 失败: {proc.stderr[-500:]}")
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def build_timeline() -> list[dict]:
    """Raw per-turn snapshot data (for users who want to render their own video)."""
    gs = st.get_game_state()
    hist = {h["turn"]: h for h in st.get_history()}
    out = []
    for t in range(0, gs["turn"] + 1):
        states = st.get_states_at(t)
        y, m = date_for_turn(t)
        h = hist.get(t, {})
        out.append({
            "turn": t, "year": y, "month": m, "reign": reign_str(y, m),
            "narrative": h.get("narrative"), "narrative_plain": h.get("narrative_plain"),
            "events": h.get("events", []),
            "factions": {k: {"name": s["name"], "economy": s["economy"],
                             "military": s["military"], "tech": s["tech"],
                             "stability": s["stability"], "treasury": s["treasury"],
                             "note": s.get("note")} for k, s in states.items()},
        })
    return out
