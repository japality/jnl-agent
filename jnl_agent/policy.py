"""BeanAlis safety grades, ported to a coding workspace.

Desktop BeanAlis (`beanalis-policy`) grades an action from the *real*
tool id and arguments — never from model hints such as readOnlyHint.
This module keeps that contract.

    L0  observe   list / search
    L1  read      read a file inside the workspace
    L2  mutate    write / patch inside the workspace (not secrets)
    L3  dangerous shell, delete, secrets, system paths, escapes

The session has a *ceiling*. An action whose grade is above the ceiling
is refused. The model cannot raise the ceiling.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, Mapping, Optional


class Grade(IntEnum):
    L0 = 0
    L1 = 1
    L2 = 2
    L3 = 3

    def label(self) -> str:
        return f"L{int(self)}"


class PolicyDenied(Exception):
    """Raised when an action exceeds the session ceiling or is forbidden."""


_SECRET_MARKERS = (
    "id_rsa",
    "id_ed25519",
    ".ssh",
    "shadow",
    "credentials",
    ".gnupg",
    "netrc",
    ".env",
    "auth.json",
    "secrets.json",
)

_DANGEROUS_BINS = frozenset(
    {
        "rm",
        "mkfs",
        "dd",
        "shutdown",
        "reboot",
        "passwd",
        "sudo",
        "su",
        "chmod",
        "chown",
        "wipe",
    }
)

_SYSTEM_PREFIXES = ("/etc", "/usr", "/boot", "/sys", "/proc", "/dev")


def _as_path(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def looks_like_secret(path: str) -> bool:
    lowered = path.lower()
    return any(marker in lowered for marker in _SECRET_MARKERS)


def looks_like_system(path: str) -> bool:
    if ".." in path.replace("\\", "/").split("/"):
        return True
    return any(path.startswith(prefix) for prefix in _SYSTEM_PREFIXES)


def first_token(cmd: str) -> str:
    cmd = cmd.strip()
    if not cmd:
        return ""
    return Path(cmd.split()[0]).name


def grade_action(action: Mapping[str, Any]) -> Grade:
    """Grade from the action payload. Model-supplied 'grade' keys are ignored."""
    op = str(action.get("op") or action.get("tool") or "").strip().lower()
    path = _as_path(action.get("path"))
    cmd = _as_path(action.get("cmd") or action.get("command"))

    if op in {"note", "verify", "status", "assert"}:
        return Grade.L0
    if op in {"list", "search", "workspace_list"}:
        return Grade.L0
    if op in {"read"}:
        if looks_like_secret(path) or looks_like_system(path):
            return Grade.L3
        return Grade.L1
    if op in {"run", "shell", "exec"}:
        bin_name = first_token(cmd)
        if bin_name in _DANGEROUS_BINS or looks_like_secret(cmd):
            return Grade.L3
        return Grade.L3
    if op in {"delete", "rm", "wipe"}:
        return Grade.L3
    if op in {"write", "patch", "apply_patch", "replace"}:
        if looks_like_secret(path) or looks_like_system(path):
            return Grade.L3
        if path.startswith(".") or "/." in path.replace("\\", "/"):
            return Grade.L3
        return Grade.L2
    # Unknown ops are treated as L2 mutations, never silently L0.
    return Grade.L2


@dataclass
class Policy:
    """Session policy. Ceiling is set by the human, not the model."""

    root: Path
    ceiling: Grade = Grade.L2
    allow_l3: bool = False
    auto_apply: bool = False

    def __post_init__(self) -> None:
        self.root = Path(self.root).resolve()
        if not self.allow_l3 and self.ceiling >= Grade.L3:
            self.ceiling = Grade.L2

    def confine(self, path: str) -> Path:
        raw = Path(path)
        target = (self.root / raw).resolve() if not raw.is_absolute() else raw.resolve()
        try:
            target.relative_to(self.root)
        except ValueError as exc:
            raise PolicyDenied(
                f"path {path!r} escapes the workspace {self.root}"
            ) from exc
        return target

    def enforce(self, action: Mapping[str, Any]) -> Grade:
        level = grade_action(action)
        if level > self.ceiling:
            raise PolicyDenied(
                f"{action.get('op')!r} is {level.label()}, "
                f"session ceiling is {self.ceiling.label()}"
            )
        if level is Grade.L3 and not self.allow_l3:
            raise PolicyDenied(
                "L3 actions need --allow-l3 (shell / secrets / delete)"
            )
        path = action.get("path")
        if path:
            self.confine(str(path))
        return level


def parse_grade(text: str) -> Grade:
    key = (text or "L2").strip().upper().replace("LEVEL", "").replace(" ", "")
    mapping = {
        "0": Grade.L0,
        "L0": Grade.L0,
        "1": Grade.L1,
        "L1": Grade.L1,
        "2": Grade.L2,
        "L2": Grade.L2,
        "3": Grade.L3,
        "L3": Grade.L3,
    }
    if key not in mapping:
        raise ValueError(f"unknown grade {text!r}; use L0 L1 L2 L3")
    return mapping[key]


def grade_help() -> str:
    return (
        "BeanAlis grades (model cannot self-promote):\n"
        "  L0  observe   list / search the workspace\n"
        "  L1  read      read a file inside the workspace\n"
        "  L2  mutate    write or patch (default ceiling)\n"
        "  L3  dangerous shell, delete, secrets, system paths\n"
        "YOLO / auto-apply never raises the ceiling and never enables L3."
    )
