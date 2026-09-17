from __future__ import annotations

import json
from typing import Any

from .config import cerebras_api_key, cerebras_model

SYSTEM = (
    "You are a Davis & Shirtliff East Africa water & energy sales engineer. "
    "Be factual, concise, and never invent prices, SLAs, or guarantees. "
    "Return JSON only when asked. Do not use markdown fences."
)


def has_llm() -> bool:
    return bool(cerebras_api_key())


def complete(prompt: str, *, json_mode: bool = False, temperature: float = 0.2) -> str:
    key = cerebras_api_key()
    if not key:
        raise RuntimeError("CEREBRAS_API_KEY is not set")

    from cerebras.cloud.sdk import Cerebras

    client = Cerebras(api_key=key)
    kwargs: dict[str, Any] = {
        "model": cerebras_model(),
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": 2200,
    }
    kwargs["reasoning_effort"] = "none"
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    resp = client.chat.completions.create(**kwargs)
    content = resp.choices[0].message.content
    if isinstance(content, list):
        parts = []
        for p in content:
            if isinstance(p, dict) and p.get("text"):
                parts.append(p["text"])
            else:
                parts.append(str(p))
        return "".join(parts).strip()
    return str(content or "").strip()


def complete_json(prompt: str) -> dict:
    raw = complete(prompt, json_mode=True)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {"value": data}
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            return json.loads(raw[start : end + 1])
        raise
