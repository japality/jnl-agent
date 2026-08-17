"""Perform a compiled score with Japalitynil + policy-graded tools."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from japalitynil import Executor, parse, plan
from japalitynil.providers import (
    AnthropicProvider,
    MockLLMProvider,
    OllamaProvider,
    provider_from_config,
)

from .mock import CodingMockProvider
from .policy import Grade, Policy
from .scores import compile_score
from .tools import Workspace, coding_tools


@dataclass
class PerformResult:
    return_value: Any
    score: str
    plan_text: str
    audit: list
    trace: list
    session_dir: Optional[Path] = field(default=None)
    intent: str = ""


def build_provider(name: str, model: Optional[str], base_url: Optional[str]):
    name = (name or "mock").lower()
    if name in {"mock", "coding-mock"}:
        return CodingMockProvider()
    if name == "jnl-mock":
        return MockLLMProvider()
    if name == "ollama":
        return OllamaProvider(model=model or "llama3.1", base_url=base_url or "http://localhost:11434")
    if name == "anthropic":
        return AnthropicProvider(model=model)
    if name in {"openai", "openai-compatible"}:
        return provider_from_config(
            "openai-compatible" if name == "openai-compatible" else "openai",
            model=model,
            base_url=base_url,
        )
    raise ValueError(f"unknown provider {name!r}")


def compile_and_plan(intent: str):
    source = compile_score(intent)
    program = parse(source, filename="<jnla-score>")
    compiled = plan(program)
    return source, compiled


def perform(
    intent: str,
    *,
    root: Path,
    ceiling: Grade = Grade.L2,
    allow_l3: bool = False,
    provider: str = "mock",
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    llm=None,
    record_dir: Optional[Path] = None,
) -> PerformResult:
    root = Path(root).resolve()
    policy = Policy(root=root, ceiling=ceiling, allow_l3=allow_l3)
    workspace = Workspace(policy)
    source, compiled = compile_and_plan(intent)

    os.environ["JNLA_ROOT"] = str(root)
    os.environ["JNLA_GRADE"] = ceiling.label()

    engine = llm or build_provider(provider, model, base_url)
    executor = Executor(llm=engine, tools=coding_tools(workspace), llm_verify=False)
    result = executor.run(compiled, input_value=intent, base_dir=str(root))
    performed = PerformResult(
        return_value=result.return_value,
        score=source,
        plan_text=compiled.render(),
        audit=workspace.audit,
        trace=list(result.trace),
        intent=intent,
    )
    if record_dir is not None:
        dump_session(Path(record_dir), performed)
        performed.session_dir = Path(record_dir)
    return performed


def default_session_dir(root: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(root) / ".jnla" / "sessions" / stamp


def latest_session_dir(root: Path) -> Optional[Path]:
    base = Path(root) / ".jnla" / "sessions"
    if not base.is_dir():
        return None
    sessions = sorted((p for p in base.iterdir() if p.is_dir()), reverse=True)
    return sessions[0] if sessions else None


def dump_session(dest: Path, performed: PerformResult) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "score.jnl").write_text(performed.score, encoding="utf-8")
    (dest / "plan.txt").write_text(performed.plan_text, encoding="utf-8")
    payload = {
        "intent": performed.intent,
        "return_value": performed.return_value,
        "audit": performed.audit,
        "trace": performed.trace,
    }
    (dest / "result.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def load_session(dest: Path) -> dict:
    payload = json.loads((Path(dest) / "result.json").read_text(encoding="utf-8"))
    plan_text = ""
    plan_path = Path(dest) / "plan.txt"
    if plan_path.is_file():
        plan_text = plan_path.read_text(encoding="utf-8")
    payload["plan_text"] = plan_text
    payload["session_dir"] = str(Path(dest).resolve())
    return payload
