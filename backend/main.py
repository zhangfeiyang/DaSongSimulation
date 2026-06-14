"""FastAPI entrypoint for the Da Song Simulator.

Run from the backend/ directory:
    uvicorn main:app --reload --port 8000
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import db
import config
from config import DATA_DIR, load_llm_config, save_llm_config, LLMConfig
from pydantic import BaseModel
from models import TurnRequest, LLMConfigUpdate, SaveRequest
from game import state as st
from game import engine
from game import sim
from game import tech as techmod
from game import war
from llm.client import LLMError

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"

app = FastAPI(title="大宋模拟器 Da Song Simulator")


@app.on_event("startup")
def _startup() -> None:
    db.init_db()
    if not db.is_initialised():
        st.reset_world()
    # ensure the territory geojson exists even on an already-seeded db
    if not (DATA_DIR / "factions.geojson").exists():
        from game import territory
        territory.write()


# ---- data / map ----------------------------------------------------------

@app.get("/api/world.geojson")
def world_geojson():
    return FileResponse(DATA_DIR / "world.geojson", media_type="application/geo+json")


@app.get("/api/factions.geojson")
def factions_geojson():
    return FileResponse(DATA_DIR / "factions.geojson", media_type="application/geo+json")


# ---- game state ----------------------------------------------------------

@app.get("/api/state")
def get_state():
    gs = st.get_game_state()
    states = st.get_states_at(gs["turn"])
    factions = []
    for key, s in states.items():
        factions.append({
            "faction_key": key, "name": s["name"], "name_en": s["name_en"],
            "color": s["color"], "is_player": bool(s["is_player"]),
            "capital": s["capital"], "info": s["info"],
            "treasury": s["treasury"], "population": s["population"],
            "economy": s["economy"], "military": s["military"], "army": s["army"],
            "tech": s["tech"], "stability": s["stability"], "welfare": s["welfare"],
            "relation": s["relation"], "note": s.get("note"),
            "bankrupt": s["treasury"] <= 0,
            "occupied": (not s["is_player"]) and s["military"] <= 0.5,
            "at_war": bool(s.get("at_war", 0)),
            "budget": sim.budget(s),
        })
    # player first, then by economy desc
    factions.sort(key=lambda f: (not f["is_player"], -f["economy"]))
    return {
        "turn": gs["turn"], "year": gs["year"], "month": gs["month"],
        "player": gs["player"], "factions": factions,
        "last_turn": st.get_last_turn_log(),
        "active_policies": st.get_active_policies(gs["turn"]),
    }


@app.post("/api/turn")
def post_turn(req: TurnRequest):
    try:
        return engine.run_turn(req.policy_text, req.chosen_options)
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"推演出错: {e}")


@app.get("/api/history")
def get_history():
    return st.get_history()


@app.get("/api/series/{faction_key}")
def get_series(faction_key: str):
    keys = ["treasury", "economy", "military", "tech", "stability", "welfare"]
    return st.get_series(faction_key, keys)


@app.get("/api/lore/{faction_key}")
def get_lore(faction_key: str):
    from game import lore
    return {"key": faction_key, "detail": lore.get_detail(faction_key)}


# ---- 科技树 ----

@app.get("/api/tech")
def get_tech():
    gs = st.get_game_state()
    song = st.get_states_at(gs["turn"]).get("song")
    bonus = techmod.policy_science_bonus(st.get_active_policies(gs["turn"]))
    return techmod.tree_view(st.get_tech_state(), song, bonus)


class ResearchReq(BaseModel):
    tech_id: str | None = None


@app.post("/api/tech/research")
def set_research(req: ResearchReq):
    st.set_research(req.tech_id)
    gs = st.get_game_state()
    song = st.get_states_at(gs["turn"]).get("song")
    bonus = techmod.policy_science_bonus(st.get_active_policies(gs["turn"]))
    return techmod.tree_view(st.get_tech_state(), song, bonus)


# ---- 议和 / 割地赔款 ----

class PeaceReq(BaseModel):
    faction: str
    cede_fraction: float = 0.0
    indemnity: float = 0.0
    song_pays: bool = False


class WarReq(BaseModel):
    faction: str
    commit_army: float = 0.0
    intensity: str = "battle"


@app.post("/api/war")
def post_war(req: WarReq):
    res = war.launch_campaign(req.faction, req.commit_army, req.intensity)
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("error", "出兵失败"))
    return res


@app.post("/api/peace")
def post_peace(req: PeaceReq):
    res = war.negotiate_peace(req.faction, req.cede_fraction, req.indemnity, req.song_pays)
    if not res.get("ok"):
        raise HTTPException(status_code=400, detail=res.get("error", "议和失败"))
    return res


# ---- snapshots / evolution video -----------------------------------------

@app.get("/api/timeline")
def get_timeline():
    from game import video
    return video.build_timeline()


@app.post("/api/video")
def make_video(seconds_per_turn: float = 0.9):
    from game import video
    try:
        path = video.build_video(seconds_per_turn=seconds_per_turn)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"生成视频失败: {e}")
    return FileResponse(path, media_type="video/mp4", filename="dasong_evolution.mp4")


@app.post("/api/rewind/{turn}")
def post_rewind(turn: int):
    if not st.rewind_to(turn):
        raise HTTPException(status_code=400, detail="无法回溯到该回合（须为早于当前的历史回合）")
    return {"ok": True}


@app.post("/api/reset")
def post_reset():
    st.reset_world()
    return {"ok": True}


# ---- saves ---------------------------------------------------------------

@app.get("/api/saves")
def get_saves():
    return st.list_saves()


@app.post("/api/saves")
def create_save(req: SaveRequest):
    return st.save_game(req.name)


@app.post("/api/saves/{save_id}/load")
def load_save(save_id: int):
    if not st.load_game(save_id):
        raise HTTPException(status_code=404, detail="存档不存在")
    return {"ok": True}


@app.delete("/api/saves/{save_id}")
def remove_save(save_id: int):
    st.delete_save(save_id)
    return {"ok": True}


# ---- LLM config ----------------------------------------------------------

@app.get("/api/config")
def get_config():
    return load_llm_config().public_dict()


@app.post("/api/config")
def post_config(update: LLMConfigUpdate):
    cfg = load_llm_config()
    data = update.model_dump(exclude_none=True)
    # never overwrite a stored key with the masked placeholder
    if data.get("api_key") in ("***", ""):
        data.pop("api_key", None)
    for k, v in data.items():
        setattr(cfg, k, v)
    save_llm_config(cfg)
    return cfg.public_dict()


@app.get("/healthz")
def healthz():
    return {"ok": True}


# ---- static frontend (mounted last so /api/* and routes above win) --------

if FRONTEND.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND), html=True), name="frontend")
