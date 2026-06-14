"""Unified LLM client. Supports three providers:

  - "anthropic": Anthropic Messages API   (POST /v1/messages)
  - "openai":    OpenAI-compatible Chat Completions (works with OpenAI, DeepSeek,
                 Moonshot, GLM gateways, vLLM, Ollama, etc. via base_url)
  - "mock":      deterministic local推演, no API key, so the game is playable offline

Both real providers use **streaming** (SSE). Reasoning models (e.g. glm-5.1, DeepSeek-R1)
can spend a long time thinking before emitting the answer; a non-streaming request would
hit the HTTP read timeout. Streaming keeps tokens flowing so the connection never idles,
and we accumulate only the final answer text (reasoning/thinking blocks are dropped).

Raw HTTP via httpx is used deliberately so a single dependency covers both API shapes.
"""
from __future__ import annotations

import json
import httpx

from config import LLMConfig

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
OPENAI_DEFAULT_BASE = "https://api.openai.com/v1"


class LLMError(RuntimeError):
    pass


def _timeout(cfg: LLMConfig) -> httpx.Timeout:
    # `read` is the max gap allowed *between* streamed chunks, not the whole call.
    read = float(getattr(cfg, "timeout", 0) or 0) or 300.0
    return httpx.Timeout(connect=20.0, read=read, write=60.0, pool=20.0)


def complete(system: str, user: str, cfg: LLMConfig) -> str:
    provider = (cfg.provider or "mock").lower()
    if provider == "mock":
        from llm.mock import mock_complete
        return mock_complete(system, user)
    if provider == "anthropic":
        return _anthropic(system, user, cfg)
    if provider == "openai":
        return _openai(system, user, cfg)
    raise LLMError(f"未知的 LLM provider: {provider}")


def _read_error_body(r: httpx.Response) -> str:
    try:
        r.read()
        return r.text[:600]
    except Exception:
        return "(无法读取错误响应体)"


def _anthropic(system: str, user: str, cfg: LLMConfig) -> str:
    if not cfg.api_key:
        raise LLMError("Anthropic 需要 api_key，请在配置中填写或切换为 mock。")
    url = (cfg.base_url.rstrip("/") + "/v1/messages") if cfg.base_url else ANTHROPIC_URL
    headers = {
        "x-api-key": cfg.api_key,
        # some 3rd-party gateways authenticate via Bearer; sending both is harmless.
        "authorization": f"Bearer {cfg.api_key}",
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    body = {
        "model": cfg.model,
        "max_tokens": cfg.max_tokens,
        "stream": True,
        "system": [{"type": "text", "text": system,
                    "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": user}],
    }
    text: list[str] = []
    try:
        with httpx.stream("POST", url, headers=headers, json=body, timeout=_timeout(cfg)) as r:
            if r.status_code >= 400:
                raise LLMError(f"Anthropic {r.status_code}: {_read_error_body(r)}")
            for line in r.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload in ("", "[DONE]"):
                    continue
                try:
                    evt = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                etype = evt.get("type")
                if etype == "content_block_delta":
                    delta = evt.get("delta", {})
                    if delta.get("type") == "text_delta":
                        text.append(delta.get("text", ""))
                elif etype == "error":
                    raise LLMError(f"Anthropic 流式错误: {evt.get('error')}")
    except httpx.HTTPError as e:
        raise LLMError(f"Anthropic 请求失败: {e}（模型推理较慢可在设置调大 timeout，"
                       f"或确认 Base URL / 模型名正确）") from e
    out = "".join(text).strip()
    if not out:
        raise LLMError("Anthropic 返回的正文为空（该模型可能把全部 token 用在了思考上，"
                       "请调大 max_tokens，或换一个模型）。")
    return out


def _openai(system: str, user: str, cfg: LLMConfig) -> str:
    if not cfg.api_key:
        raise LLMError("OpenAI 兼容接口需要 api_key，请在配置中填写或切换为 mock。")
    base = cfg.base_url.rstrip("/") if cfg.base_url else OPENAI_DEFAULT_BASE
    headers = {"Authorization": f"Bearer {cfg.api_key}", "Content-Type": "application/json"}
    body = {
        "model": cfg.model,
        "temperature": cfg.temperature,
        "max_tokens": cfg.max_tokens,
        "stream": True,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    text: list[str] = []
    try:
        with httpx.stream("POST", base + "/chat/completions", headers=headers,
                          json=body, timeout=_timeout(cfg)) as r:
            if r.status_code >= 400:
                raise LLMError(f"OpenAI {r.status_code}: {_read_error_body(r)}")
            for line in r.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload in ("", "[DONE]"):
                    continue
                try:
                    evt = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                choices = evt.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                # final answer only; ignore reasoning_content from reasoning models
                if delta.get("content"):
                    text.append(delta["content"])
    except httpx.HTTPError as e:
        raise LLMError(f"OpenAI 兼容接口请求失败: {e}（模型推理较慢可在设置调大 timeout，"
                       f"或确认 Base URL / 模型名正确）") from e
    out = "".join(text).strip()
    if not out:
        raise LLMError("OpenAI 兼容接口返回正文为空（该模型可能把 token 用在了思考上，"
                       "请调大 max_tokens 或更换模型）。")
    return out


def extract_json(text: str) -> dict:
    """Pull the first JSON object out of a model response (handles ```json fences)."""
    if not text:
        raise LLMError("LLM 返回为空")
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1]
        if t.startswith("json"):
            t = t[4:]
        t = t.strip()
    start, end = t.find("{"), t.rfind("}")
    if start != -1 and end != -1 and end > start:
        t = t[start:end + 1]
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    # LLM 常见错误：字符串内含未转义的引号、尾逗号等。用 json-repair 兜底修复。
    try:
        from json_repair import repair_json
        repaired = repair_json(t)
        obj = json.loads(repaired)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    raise LLMError(f"无法解析 LLM 返回的 JSON（已尝试自动修复仍失败）。原文: {text[:800]}")
