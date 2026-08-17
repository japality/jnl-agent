"""JNL Agent — score-then-perform vibe coding (CLI, not an editor)."""

from __future__ import annotations

import sys
from pathlib import Path

__version__ = "0.0.1"

_JNL_ROOT = Path(__file__).resolve().parents[2] / "japalitynil"
if _JNL_ROOT.is_dir() and str(_JNL_ROOT) not in sys.path:
    sys.path.insert(0, str(_JNL_ROOT))

from .policy import Grade, Policy, PolicyDenied, grade_action  # noqa: E402
from .scores import compile_score  # noqa: E402

__all__ = [
    "__version__",
    "Grade",
    "Policy",
    "PolicyDenied",
    "grade_action",
    "compile_score",
]
