"""Pydantic request/response models for the API."""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel


class TurnRequest(BaseModel):
    policy_text: str = ""
    chosen_options: list[str] = []


class SaveRequest(BaseModel):
    name: str = ""


class LLMConfigUpdate(BaseModel):
    provider: str | None = None
    model: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    timeout: float | None = None


class FactionState(BaseModel):
    faction_key: str
    name: str
    name_en: str | None = None
    color: str | None = None
    is_player: bool = False
    capital: str | None = None
    info: str | None = None
    treasury: float = 0
    population: float = 0
    economy: float = 0
    military: float = 0
    army: float = 0
    tech: float = 0
    stability: float = 0
    welfare: float = 0
    relation: float = 0
    note: str | None = None


class StateResponse(BaseModel):
    turn: int
    year: int
    month: int
    player: str
    factions: list[FactionState]
    last_turn: dict[str, Any] | None = None
