"""Minimal OpenAI-compatible chat-completions client (Ollama by default). Nothing here is required for the loop.

RESOLVELOOP_LLM_BASE_URL may list several base URLs separated by commas (e.g. a GPU box through an SSH tunnel first,
a CPU fallback second). The first whose GET {base}/models answers within 3 s is used. Tests monkeypatch `complete`.
"""
import re
import time
from typing import Optional

import httpx

from .. import config

PROBE_TIMEOUT = 3.0
THINK_RE = re.compile(r"<think>.*?</think>\s*", re.S)


def base_urls() -> list:
    return [u.strip().rstrip("/") for u in config.LLM_BASE_URL.split(",") if u.strip()]


def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    if config.LLM_API_KEY:
        h["Authorization"] = f"Bearer {config.LLM_API_KEY}"
    return h


def probe(base: str, timeout: float = PROBE_TIMEOUT) -> dict:
    """GET {base}/models. Returns {url, reachable, latency_ms, error}."""
    t0 = time.monotonic()
    try:
        r = httpx.get(f"{base}/models", headers=_headers(), timeout=timeout)
        ok = r.status_code < 500
        return {"url": base, "reachable": ok, "latency_ms": round((time.monotonic() - t0) * 1000), "error": None if ok else f"HTTP {r.status_code}"}
    except Exception as e:  # noqa: BLE001 - any transport failure means "not reachable"
        return {"url": base, "reachable": False, "latency_ms": round((time.monotonic() - t0) * 1000), "error": type(e).__name__}


def active_base() -> Optional[str]:
    for base in base_urls():
        if probe(base)["reachable"]:
            return base
    return None


def health() -> dict:
    probes = [probe(b) for b in base_urls()]
    active = next((p["url"] for p in probes if p["reachable"]), None)
    return {
        "configured_base_url": config.LLM_BASE_URL, "configured_base_urls": base_urls(), "model": config.LLM_MODEL,
        "reachable": active is not None, "active_base_url": active,
        "latency_ms": next((p["latency_ms"] for p in probes if p["reachable"]), None), "endpoints": probes,
    }


def strip_think(text: str) -> str:
    """Remove any <think>...</think> block Qwen3 may emit (also an unterminated one)."""
    text = THINK_RE.sub("", text or "")
    if "<think>" in text and "</think>" not in text:
        text = text.split("<think>", 1)[0]
    return text.strip()


class LLMError(RuntimeError):
    """The model could not be reached or returned no usable text."""


def complete(messages: list, model: Optional[str] = None, max_tokens: int = 1200) -> str:
    """One chat completion; returns the assistant text with any think-block stripped. Raises LLMError."""
    base = active_base()
    if not base:
        raise LLMError(f"no LLM endpoint reachable among {base_urls()}")
    msgs = [dict(m) for m in messages]
    for m in reversed(msgs):
        if m.get("role") == "user":
            m["content"] = m["content"].rstrip() + " /no_think"  # Qwen3 on Ollama: disable thinking
            break
    body = {"model": model or config.LLM_MODEL, "messages": msgs, "temperature": 0, "max_tokens": max_tokens, "stream": False,
            "response_format": {"type": "json_object"}}
    try:
        r = httpx.post(f"{base}/chat/completions", json=body, headers=_headers(), timeout=config.LLM_TIMEOUT)
        if r.status_code == 400:  # server rejects response_format: retry without it, silently
            body.pop("response_format")
            r = httpx.post(f"{base}/chat/completions", json=body, headers=_headers(), timeout=config.LLM_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        text = data["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as e:
        raise LLMError(f"{type(e).__name__}: {e}") from e
    return strip_think(text)
