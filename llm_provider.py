#!/usr/bin/env python3
"""
Shared free-LLM provider for free-ai-apps.
Zero dependencies (stdlib only). All providers are OpenAI-compatible chat endpoints.

Config via environment:
    LLM_PROVIDER = groq | gemini | mistral | openrouter | ollama | none  (default: none)
    LLM_MODEL    = model name for the provider (see research file for current free models)
    LLM_API_KEY  = API key (not needed for ollama / none)

    ~/workspace/research/2026-09-28-free-llm-api-landscape.md has the current
    free-tier details, model names and signup links (no credit card needed).

Usage:
    from llm_provider import chat
    reply = chat([{"role": "system", "content": "..."},
                  {"role": "user", "content": "..."}])
    # reply is a str, or None when no provider/key is configured or the call fails.
    # Apps MUST work in a useful rule-based fallback mode when chat() returns None.
"""
import json
import os
import urllib.request
import urllib.error

PROVIDERS = {
    "groq":       "https://api.groq.com/openai/v1",
    "gemini":     "https://generativelanguage.googleapis.com/v1beta/openai",
    "mistral":    "https://api.mistral.ai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "ollama":     "http://localhost:11434/v1",
}

_config_cache = {}


def get_config():
    if _config_cache:
        return _config_cache
    provider = os.environ.get("LLM_PROVIDER", "none").strip().lower()
    cfg = {"provider": provider, "ok": False, "reason": "LLM_PROVIDER not set (none)"}
    if provider in PROVIDERS:
        key = os.environ.get("LLM_API_KEY", "").strip()
        model = os.environ.get("LLM_MODEL", "").strip()
        if provider == "ollama":
            key = key or "ollama"
        if not key:
            cfg["reason"] = "LLM_API_KEY not set for provider '%s'" % provider
        elif not model:
            cfg["reason"] = "LLM_MODEL not set for provider '%s'" % provider
        else:
            cfg.update({"ok": True, "base": PROVIDERS[provider],
                        "key": key, "model": model, "reason": ""})
    _config_cache.update(cfg)
    return _config_cache


def chat(messages, temperature=0.7, max_tokens=800, timeout=45):
    """Return assistant reply str, or None if LLM is unavailable/fails."""
    cfg = get_config()
    if not cfg["ok"]:
        return None
    payload = json.dumps({
        "model": cfg["model"],
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }).encode("utf-8")
    req = urllib.request.Request(
        cfg["base"] + "/chat/completions", data=payload,
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + cfg["key"]})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


def status():
    """Human-readable one-liner about LLM availability (safe to show user)."""
    cfg = get_config()
    if cfg["ok"]:
        return "LLM ready: %s (%s)" % (cfg["provider"], cfg["model"])
    return "LLM off (rule-based mode): %s" % cfg["reason"]
