"""Workspace tools. Every call is graded before it touches the disk."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List

from .actions import parse_action
from .policy import Policy, PolicyDenied


_SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    ".venv",
    "venv",
    ".jnla",
}


class Workspace:
    def __init__(self, policy: Policy) -> None:
        self.policy = policy
        self.audit: List[Dict[str, Any]] = []

    def act(self, **kwargs: Any) -> Dict[str, Any]:
        raw = next(iter(kwargs.values()), "")
        action = parse_action(raw)
        try:
            level = self.policy.enforce(action)
        except PolicyDenied as exc:
            record = {
                "ok": False,
                "denied": True,
                "error": str(exc),
                "action": action,
            }
            self.audit.append(record)
            return record
        result = self._dispatch(action)
        result["grade"] = level.label()
        result["action"] = action.get("op")
        self.audit.append(result)
        return result

    def _dispatch(self, action: Dict[str, Any]) -> Dict[str, Any]:
        op = str(action.get("op") or "").lower()
        if op in {"list", "workspace_list"}:
            return self.list_tree(action.get("path") or ".")
        if op == "search":
            return self.search(str(action.get("query") or action.get("path") or ""))
        if op == "read":
            return self.read(str(action.get("path") or ""))
        if op == "write":
            return self.write(str(action.get("path") or ""), action.get("content") or "")
        if op == "replace":
            return self.replace(
                str(action.get("path") or ""),
                action.get("old") or action.get("find") or "",
                action.get("new") or action.get("replace") or "",
            )
        if op in {"patch", "apply_patch"}:
            return self.replace(
                str(action.get("path") or ""),
                action.get("old") or "",
                action.get("new") or action.get("content") or "",
            )
        if op == "assert":
            return self.assert_file(
                str(action.get("path") or ""),
                contains=action.get("contains"),
            )
        if op in {"run", "shell", "exec"}:
            return self.run(str(action.get("cmd") or action.get("command") or ""))
        if op in {"note", "verify", "status"}:
            return {"ok": True, "note": str(action.get("text") or action.get("note") or "")}
        return {"ok": False, "error": f"unknown op {op!r}"}

    def list_tree(self, rel: str = ".", limit: int = 80) -> Dict[str, Any]:
        base = self.policy.confine(rel)
        if not base.exists():
            return {"ok": False, "error": f"{rel} does not exist"}
        files: List[str] = []
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
            for name in filenames:
                full = Path(dirpath) / name
                try:
                    rel_path = str(full.relative_to(self.policy.root))
                except ValueError:
                    continue
                files.append(rel_path)
                if len(files) >= limit:
                    return {"ok": True, "files": files, "truncated": True}
        return {"ok": True, "files": files, "truncated": False}

    def search(self, query: str, limit: int = 20) -> Dict[str, Any]:
        query = query.strip()
        if not query:
            return {"ok": False, "error": "empty search query"}
        hits = []
        listing = self.list_tree(".", limit=200)
        for rel in listing.get("files") or []:
            path = self.policy.root / rel
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if query.lower() in rel.lower() or query in text:
                line_no = 1
                snippet = ""
                for i, line in enumerate(text.splitlines(), 1):
                    if query in line or query.lower() in line.lower():
                        line_no = i
                        snippet = line.strip()[:200]
                        break
                hits.append({"path": rel, "line": line_no, "snippet": snippet})
                if len(hits) >= limit:
                    break
        return {"ok": True, "query": query, "hits": hits}

    def read(self, rel: str, max_chars: int = 8000) -> Dict[str, Any]:
        path = self.policy.confine(rel)
        if not path.is_file():
            return {"ok": False, "error": f"{rel} is not a file"}
        text = path.read_text(encoding="utf-8", errors="replace")
        truncated = len(text) > max_chars
        return {
            "ok": True,
            "path": rel,
            "content": text[:max_chars],
            "truncated": truncated,
        }

    def replace(self, rel: str, old: Any, new: Any) -> Dict[str, Any]:
        path = self.policy.confine(rel)
        if not path.is_file():
            return {"ok": False, "error": f"{rel} is not a file", "path": rel}
        old_text = str(old)
        new_text = str(new)
        if not old_text:
            return {"ok": False, "error": "replace requires a non-empty old string", "path": rel}
        original = path.read_text(encoding="utf-8")
        count = original.count(old_text)
        if count == 0:
            return {
                "ok": False,
                "error": "old string not found",
                "path": rel,
            }
        if count != 1:
            return {
                "ok": False,
                "error": f"old string matches {count} times; need exactly one",
                "path": rel,
            }
        path.write_text(original.replace(old_text, new_text, 1), encoding="utf-8")
        return {"ok": True, "path": rel, "replaced": 1}

    def assert_file(self, rel: str, contains: Any = None) -> Dict[str, Any]:
        if not rel:
            return {"ok": False, "error": "assert requires a path"}
        path = self.policy.confine(rel)
        if not path.is_file():
            return {"ok": False, "error": f"{rel} is not a file", "path": rel}
        text = path.read_text(encoding="utf-8", errors="replace")
        needle = "" if contains is None else str(contains)
        if needle and needle not in text:
            return {
                "ok": False,
                "path": rel,
                "contains": needle,
                "error": f"{rel} does not contain {needle!r}",
            }
        return {"ok": True, "path": rel, "contains": needle}

    def write(self, rel: str, content: Any) -> Dict[str, Any]:
        path = self.policy.confine(rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
        path.write_text(data, encoding="utf-8")
        return {"ok": True, "path": rel, "bytes": len(data.encode("utf-8"))}

    def run(self, cmd: str, timeout: float = 30.0) -> Dict[str, Any]:
        cmd = cmd.strip()
        if not cmd:
            return {"ok": False, "error": "empty command"}
        try:
            proc = subprocess.run(
                cmd,
                shell=True,
                cwd=str(self.policy.root),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"timeout after {timeout}s", "cmd": cmd}
        return {
            "ok": proc.returncode == 0,
            "cmd": cmd,
            "exit": proc.returncode,
            "stdout": (proc.stdout or "")[-4000:],
            "stderr": (proc.stderr or "")[-2000:],
        }


def coding_tools(workspace: Workspace) -> Dict[str, Any]:
    return {"act": workspace.act}
