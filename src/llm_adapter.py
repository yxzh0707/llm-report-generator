"""Small OpenAI-compatible chat adapter for the local dissertation prototype."""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

try:
    from .runtime_config import load_project_environment, provider_settings
except ImportError:  # pragma: no cover - supports direct script-style imports
    from runtime_config import load_project_environment, provider_settings


def chat_completion(*, system: str, user: str, model: str | None = None,
                    temperature: float = 0.2, max_tokens: int = 3500,
                    enable_thinking: bool | None = None, role: str = 'generator') -> dict[str, Any]:
    load_project_environment(role=role)
    settings = provider_settings(enable_thinking=enable_thinking, role=role, model=model)
    base = settings['base_url']
    token = os.getenv(settings['api_key_env'], '')
    if not token:
        raise RuntimeError('Provider API key is not configured')
    if not model:
        model = settings['model']
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    payload.update(settings['extra_body'])
    request = urllib.request.Request(
        base + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + token},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        result = json.load(response)
    choices = result.get("choices") or []
    if not choices:
        raise RuntimeError("LLM response did not contain choices")
    return result
