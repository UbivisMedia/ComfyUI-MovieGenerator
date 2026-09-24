"""
llm_manager.py - LM Studio integration and model management for MovieGenerator.
Provides unified functions for LM Studio configuration, status checking,
model discovery, chat completions, and CLI model loading/unloading.
"""

import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from lib.settings_manager import load_settings


def get_lm_studio_config(settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Reads LM Studio configuration from settings dict or settings.json."""
    if settings is None:
        settings = load_settings()
    lms = settings.get("lm_studio", {})
    url = lms.get("url", "http://127.0.0.1:1234/v1/chat/completions")
    model_name = lms.get("model_name", "")
    try:
        temp = float(lms.get("temperature", 0.7))
    except (TypeError, ValueError):
        temp = 0.7
    return {
        "url": url,
        "model_name": model_name,
        "temperature": temp
    }


def fetch_lm_studio_models(api_url: Optional[str] = None) -> List[str]:
    """Attempts to retrieve available models from LM Studio /v1/models."""
    try:
        if not api_url:
            cfg = get_lm_studio_config()
            api_url = cfg["url"]

        m = re.match(r'^(https?://[^/]+(?:/v1)?)', api_url)
        if m:
            base_prefix = m.group(1)
            if not base_prefix.endswith('/v1'):
                models_url = f"{base_prefix}/v1/models"
            else:
                models_url = f"{base_prefix}/models"
        else:
            models_url = "http://127.0.0.1:1234/v1/models"

        req = urllib.request.Request(models_url, headers={"User-Agent": "MovieGenerator"})
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models_list: List[str] = []
            if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
                for item in data["data"]:
                    mid = item.get("id")
                    if mid and mid not in models_list:
                        models_list.append(mid)
            return models_list
    except Exception:
        return []


def check_lm_studio_status(settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Checks if LM Studio Local Server is running and lists loaded models."""
    cfg = get_lm_studio_config(settings)
    url = cfg["url"]
    base_url = url.split("/chat/completions")[0] if "/chat/completions" in url else url.rstrip("/")
    models_url = f"{base_url}/models"
    try:
        req = urllib.request.Request(models_url, headers={"User-Agent": "MovieGenerator-LLMManager"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models_list = [m.get("id") for m in data.get("data", []) if m.get("id")]
            active_model = cfg["model_name"]
            if not active_model and models_list:
                active_model = models_list[0]
            elif models_list and active_model not in models_list:
                active_model = models_list[0]
            return {
                "online": True,
                "model": active_model or "Local LLM",
                "models": models_list,
                "url": url
            }
    except Exception as e:
        return {
            "online": False,
            "model": cfg.get("model_name") or "Offline",
            "error": str(e),
            "url": url
        }


def call_lm_studio(
    messages: List[Dict[str, str]],
    url: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: int = 5000,
    timeout: Optional[int] = None
) -> str:
    """Sends a chat completion request to the LM Studio Local Server."""
    cfg = get_lm_studio_config()
    endpoint = url or cfg["url"]
    model_name = model or cfg["model_name"] or "default"
    temp = temperature if temperature is not None else cfg["temperature"]

    # Prepend anti-thinking system message if none provided to keep reasoning models fast and direct
    has_system = any(m.get("role") == "system" for m in messages)
    clean_messages = list(messages)
    if not has_system:
        clean_messages.insert(0, {
            "role": "system",
            "content": "You are a professional movie director and screenwriter assistant. Never output your internal thinking, reasoning process, or preamble. Start directly with the final response."
        })

    payload = {
        "model": model_name,
        "messages": clean_messages,
        "temperature": temp,
        "max_tokens": max_tokens
    }
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    if timeout is None:
        timeout = max(180, int(max_tokens * 0.05))

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        msg = res["choices"][0]["message"]
        content = (msg.get("content") or "").strip()
        reasoning = (msg.get("reasoning_content") or "").strip()
        if not content and reasoning:
            if "summary:" in reasoning:
                content = "summary:" + reasoning.split("summary:", 1)[1]
            elif "Summary:" in reasoning:
                content = "summary:" + reasoning.split("Summary:", 1)[1]
            else:
                content = reasoning
        return content


def lms_load(model_name: Optional[str] = None) -> bool:
    """Invokes LM Studio CLI to load a model into VRAM."""
    if not model_name:
        cfg = get_lm_studio_config()
        model_name = cfg["model_name"]

    if not model_name:
        return False

    try:
        subprocess.run(["lms", "load", model_name], check=True, capture_output=True)
        return True
    except Exception:
        return False


def lms_unload() -> bool:
    """Invokes LM Studio CLI to unload all models from VRAM."""
    try:
        subprocess.run(["lms", "unload", "--all"], check=False, capture_output=True)
        return True
    except Exception:
        return False
