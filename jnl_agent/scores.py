"""Compile a human vibe into a JNL-H score.

The score is the product. Humans can `jnla score`, `jnl check` it, lint
it, and replay it. The LLM does not get a free-form agent loop — it
plays the parts written on the page.

v0.2 pipeline: survey → inspect → patch → assert.
"""

from __future__ import annotations


def compile_score(intent: str) -> str:
    """Return JNL-H. The intent itself is *not* inlined; it arrives as @input."""
    _ = intent  # reserved for future intent-specialized scores
    return VIBE_SCORE


VIBE_SCORE = """\
edition 1
goal: fulfill the coding intent as a bounded score, not an open chat

know:
  intent = @input
  root = @env("JNLA_ROOT")
  ceiling = @env("JNLA_GRADE")

must:
  mentions op

never:
  mentions sudo
  mentions id_rsa
  promise specific dates

do llm as survey:
  using intent, root, ceiling
  STEP=survey
  look at the intent
  produce exactly one JSON action to observe the workspace
  use op list or op search
  example: {"op": "list", "path": "."}
  verify: must, never

do tool act as observed:
  using survey

do llm as inspect:
  using intent, observed, ceiling
  STEP=inspect
  pick the single most relevant existing file
  prefer implementation files over tests
  produce exactly one JSON action with op read
  example: {"op": "read", "path": "src/app.py"}
  if nothing is relevant, use op list
  verify: must, never

do tool act as focused:
  using inspect

do llm as patch:
  using intent, focused, ceiling
  STEP=patch
  produce exactly one JSON action
  prefer op replace with path, old, new (one exact substring)
  if no file exists yet and ceiling is L2, you may use op write
  if ceiling is L0 or L1, use op note
  do not propose shell
  verify: must, never

do tool act as changed:
  using patch

do llm as check:
  using intent, changed
  STEP=check
  produce exactly one JSON action with op assert
  example: {"op": "assert", "path": "src/app.py", "contains": "def target"}
  if nothing was written, use op note
  verify: must

do tool act as verdict:
  using check

return verdict
"""
