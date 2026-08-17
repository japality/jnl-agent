"""jnla — score-then-perform CLI. Not an editor."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__
from .policy import grade_help, parse_grade
from .report import summarize_audit, verdict_ok
from .runtime import (
    compile_and_plan,
    default_session_dir,
    latest_session_dir,
    load_session,
    perform,
)
from .scores import compile_score


def main(argv: Optional[List[str]] = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    parser = argparse.ArgumentParser(
        prog="jnla",
        description=(
            "Cast a vibe into a JNL score, then perform it under "
            "BeanAlis safety grades. This is a CLI, not a VS Code fork."
        ),
    )
    parser.add_argument("--version", action="version", version=f"jnla {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_score = sub.add_parser("score", help="print the compiled JNL-H score")
    p_score.add_argument("intent", help="what you want the workspace to become")

    p_plan = sub.add_parser("plan", help="compile and show the DAG; do not write")
    p_plan.add_argument("intent")

    p_run = sub.add_parser("perform", help="compile and perform the score")
    p_run.add_argument("intent")
    p_run.add_argument("--root", default=".", help="workspace root (default: .)")
    p_run.add_argument(
        "--grade",
        default="L2",
        help="session ceiling: L0 observe, L1 read, L2 write, L3 shell",
    )
    p_run.add_argument(
        "--allow-l3",
        action="store_true",
        help="permit L3 actions (shell / secrets / delete)",
    )
    p_run.add_argument(
        "--provider",
        default="mock",
        help="mock | ollama | openai | openai-compatible | anthropic",
    )
    p_run.add_argument("--model", default=None)
    p_run.add_argument("--base-url", default=None)
    p_run.add_argument(
        "--record",
        metavar="DIR",
        default=None,
        help="session directory (default: <root>/.jnla/sessions/<utc>)",
    )
    p_run.add_argument(
        "--no-record",
        action="store_true",
        help="do not write a session directory",
    )
    p_run.add_argument(
        "--json",
        action="store_true",
        help="print raw audit JSON instead of the human summary",
    )

    p_replay = sub.add_parser("replay", help="print a recorded session")
    p_replay.add_argument(
        "dir",
        nargs="?",
        default=None,
        help="session directory (default: latest under --root/.jnla/sessions)",
    )
    p_replay.add_argument("--root", default=".", help="workspace used to find latest session")
    p_replay.add_argument("--json", action="store_true")

    sub.add_parser("grades", help="explain BeanAlis L0–L3")

    args = parser.parse_args(argv)

    if args.cmd == "grades":
        print(grade_help())
        return 0

    if args.cmd == "score":
        print(compile_score(args.intent), end="")
        return 0

    if args.cmd == "plan":
        try:
            source, compiled = compile_and_plan(args.intent)
        except Exception as exc:
            print(f"compile error: {exc}", file=sys.stderr)
            return 1
        print(compiled.render())
        print()
        print("--- score (JNL-H) ---")
        print(source, end="")
        return 0

    if args.cmd == "replay":
        dest = Path(args.dir) if args.dir else latest_session_dir(Path(args.root))
        if dest is None or not (Path(dest) / "result.json").is_file():
            print("error: no session to replay", file=sys.stderr)
            return 2
        try:
            payload = load_session(dest)
        except OSError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
            return 0
        print(f"session: {payload.get('session_dir')}")
        if payload.get("intent"):
            print(f"intent:  {payload['intent']}")
        print("audit:")
        print(summarize_audit(payload.get("audit") or []))
        ok = verdict_ok(payload.get("return_value"))
        print(f"verdict: {'PASS' if ok else 'FAIL'}")
        return 0 if ok else 1

    if args.cmd == "perform":
        try:
            ceiling = parse_grade(args.grade)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        root = Path(args.root).resolve()
        if not root.is_dir():
            print(f"error: workspace {root} is not a directory", file=sys.stderr)
            return 2
        record_dir = None
        if not args.no_record:
            record_dir = Path(args.record) if args.record else default_session_dir(root)
        try:
            result = perform(
                args.intent,
                root=root,
                ceiling=ceiling,
                allow_l3=args.allow_l3,
                provider=args.provider,
                model=args.model,
                base_url=args.base_url,
                record_dir=record_dir,
            )
        except Exception as exc:
            print(f"runtime error: {exc}", file=sys.stderr)
            return 1
        if args.json:
            print(
                json.dumps(
                    {
                        "return_value": result.return_value,
                        "audit": result.audit,
                        "session": str(result.session_dir) if result.session_dir else None,
                    },
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
            )
        else:
            print(result.plan_text)
            print()
            print("audit:")
            print(summarize_audit(result.audit))
            if result.session_dir:
                print(f"\nsession: {result.session_dir}")
            print(f"verdict: {'PASS' if verdict_ok(result.return_value) else 'FAIL'}")
        return 0 if verdict_ok(result.return_value) else 1

    parser.error(f"unknown command {args.cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
