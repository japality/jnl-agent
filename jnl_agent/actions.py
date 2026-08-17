"""Parse an LLM step into a single workspace action.

The model is asked for JSON. If it rambles, we still try to recover a
safe observe action rather than executing prose as a shell command.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict


def parse_action(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    text = str(raw or "").strip()
    if not text:
        return {"op": "note", "text": ""}

    blob = _extract_json_object(text)
    if blob is not None:
        if "op" not in blob and "tool" in blob:
            blob = dict(blob)
            blob["op"] = blob["tool"]
        if "op" in blob:
            return blob

    return {"op": "note", "text": text[:2000]}


def _extract_json_object(text: str):
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return value
    except ValueError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            value = json.loads(text[start : end + 1])
            if isinstance(value, dict):
                return value
        except ValueError:
            return None
    return None
