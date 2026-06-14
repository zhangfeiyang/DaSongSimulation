"""Configuration for the Da Song Simulator.

Settings come from (in priority order):
  1. config.local.json  (gitignored, your real keys)
  2. environment variables
  3. built-in defaults

LLM_PROVIDER can be: "mock" (no key needed), "openai", or "anthropic".
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = ROOT / "data" / "game.db"
CONFIG_LOCAL = ROOT / "config.local.json"


@dataclass
class LLMConfig:
    provider: str = "mock"          # mock | openai | anthropic
    model: str = "claude-opus-4-8"
    api_key: str = ""
    base_url: str = ""              # for openai-compatible endpoints; blank = official
    temperature: float = 0.8
    max_tokens: int = 4096
    timeout: float = 300.0          # max seconds to wait between streamed chunks

    def public_dict(self) -> dict:
        """Safe to expose to the frontend (key masked)."""
        d = asdict(self)
        d["api_key"] = "***" if self.api_key else ""
        d["has_key"] = bool(self.api_key)
        return d


def _load_file() -> dict:
    if CONFIG_LOCAL.exists():
        try:
            return json.loads(CONFIG_LOCAL.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def load_llm_config() -> LLMConfig:
    f = _load_file().get("llm", {})
    return LLMConfig(
        provider=os.environ.get("LLM_PROVIDER", f.get("provider", "mock")),
        model=os.environ.get("LLM_MODEL", f.get("model", "claude-opus-4-8")),
        api_key=os.environ.get("LLM_API_KEY", f.get("api_key", "")),
        base_url=os.environ.get("LLM_BASE_URL", f.get("base_url", "")),
        temperature=float(os.environ.get("LLM_TEMPERATURE", f.get("temperature", 0.8))),
        max_tokens=int(os.environ.get("LLM_MAX_TOKENS", f.get("max_tokens", 4096))),
        timeout=float(os.environ.get("LLM_TIMEOUT", f.get("timeout", 300.0))),
    )


def save_llm_config(cfg: LLMConfig) -> None:
    data = _load_file()
    data["llm"] = asdict(cfg)
    CONFIG_LOCAL.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# Game-wide constants
START_YEAR = 1068        # 北宋 熙宁元年, 王安石变法前夕
START_MONTH = 1
PLAYER_FACTION = "song"
