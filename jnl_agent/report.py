"""Human-readable perform / replay output."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


def summarize_audit(audit: Sequence[Mapping[str, Any]]) -> str:
    lines = []
    for i, row in enumerate(audit, 1):
        grade = row.get("grade") or ("DENY" if row.get("denied") else "?")
        op = row.get("action") or (row.get("action") or {})
        if isinstance(row.get("action"), dict):
            op = row["action"].get("op")
        path = row.get("path") or ""
        if row.get("denied"):
            lines.append(f"  {i}. {grade}  {op or '?'}  DENIED — {row.get('error')}")
            continue
        if not row.get("ok", True):
            lines.append(
                f"  {i}. {grade}  {op} {path}  FAIL — {row.get('error')}"
            )
            continue
        extra = ""
        if op == "list":
            extra = f"{len(row.get('files') or [])} files"
        elif op == "read":
            extra = path
        elif op == "replace":
            extra = f"{path} (1 hunk)"
        elif op == "write":
            extra = f"{path} ({row.get('bytes', '?')} bytes)"
        elif op == "assert":
            extra = f"{path} contains {row.get('contains')!r}"
        elif op == "note":
            extra = str(row.get("note") or "")[:80]
        elif op == "run":
            extra = f"exit {row.get('exit')} {row.get('cmd')}"
        else:
            extra = path
        lines.append(f"  {i}. {grade}  {op}  {extra}".rstrip())
    return "\n".join(lines) if lines else "  (no actions)"


def verdict_ok(return_value: Any) -> bool:
    if isinstance(return_value, dict):
        if return_value.get("denied"):
            return False
        return bool(return_value.get("ok", True))
    return return_value is not None
