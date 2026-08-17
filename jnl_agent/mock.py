"""Coding-aware mock provider.

Knows the bundled `fixtures/toy` greeter so offline perform can make a
real code change. Other intents still write a note file (L2) or a note
action (L0/L1).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from japalitynil.llm_verifier import is_verify_prompt
from japalitynil.providers import LLMResponse

_HELLO_OLD = "def hello(name):\n    return f\"hi {name}\"\n"
_HELLO_NEW = (
    "def hello(name):\n"
    "    return f\"hi {name}\"\n"
    "\n"
    "\n"
    "def greet(name):\n"
    "    return f\"hello, {name}!\"\n"
)


def _extract_intent(prompt: str) -> str:
    match = re.search(r"(?im)^\s*-\s*intent\s*[:=]\s*(.+)$", prompt)
    if match:
        return match.group(1).strip()
    match = re.search(r"(?im)^\s*intent\s*[:=]\s*(.+)$", prompt)
    if match:
        return match.group(1).strip()
    return "the requested change"


def _slug(intent: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", intent.lower())
    if not words:
        return "notes"
    return "_".join(words[:4])


def _step(prompt: str) -> str:
    p = prompt.lower()
    for name in ("survey", "inspect", "patch", "check"):
        if f"step={name}" in p:
            return name
    return "patch"


def _context_blob(prompt: str) -> str:
    match = re.search(
        r"\[CONTEXT\](.*?)(?:\[MUST\]|\[NEVER\]|\[INSTRUCTION\]|$)",
        prompt,
        re.S | re.I,
    )
    return match.group(1) if match else ""


def _mentions_greeter(prompt: str) -> bool:
    blob = _context_blob(prompt).lower()
    intent = _extract_intent(prompt).lower()
    return (
        "greeter.py" in blob
        or "def hello" in blob
        or "def greet" in blob
        or "greeter.py" in intent
    )


class CodingMockProvider:
    """Deterministic provider for score-then-perform tests and first runs."""

    def complete(
        self,
        prompt: str,
        *,
        max_tokens: int = 512,
        retry_hint: Optional[str] = None,
    ) -> LLMResponse:
        if is_verify_prompt(prompt):
            return LLMResponse(text="PASS", confidence=1.0, meta={"judge": True})

        p = prompt.lower()
        intent = _extract_intent(prompt)
        step = _step(prompt)
        low_ceiling = "- ceiling: l0" in p or "- ceiling: l1" in p

        if step == "survey":
            body = {"op": "list", "path": "."}
            return LLMResponse(text=json.dumps(body), confidence=0.95)

        if step == "inspect":
            blob = _context_blob(prompt)
            found = re.findall(r"([A-Za-z0-9_./-]+\.py)", blob)
            impl = [f for f in found if not Path(f).name.startswith("test_")]
            path = (impl[0] if impl else found[0]) if found else "."
            body = (
                {"op": "read", "path": path}
                if path != "."
                else {"op": "list", "path": "."}
            )
            return LLMResponse(text=json.dumps(body), confidence=0.93)

        if step == "check":
            if _mentions_greeter(prompt):
                body = {
                    "op": "assert",
                    "path": "greeter.py",
                    "contains": "def greet",
                }
            else:
                body = {
                    "op": "note",
                    "text": f"intent recorded: {intent}. workspace action completed.",
                }
            return LLMResponse(text=json.dumps(body), confidence=0.9)

        # patch
        if low_ceiling:
            body = {"op": "note", "text": f"ceiling forbids write; intent was {intent}"}
        elif _mentions_greeter(prompt):
            body = {
                "op": "replace",
                "path": "greeter.py",
                "old": _HELLO_OLD,
                "new": _HELLO_NEW,
            }
        else:
            filename = f"{_slug(intent)}.md"
            body = {
                "op": "write",
                "path": filename,
                "content": (
                    f"# {_slug(intent).replace('_', ' ')}\n\n"
                    f"Recorded by jnla (mock performer).\n\n"
                    f"Intent: {intent}\n"
                ),
            }
        return LLMResponse(text=json.dumps(body), confidence=0.9)
