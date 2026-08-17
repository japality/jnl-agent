# JNL Agent (`jnla`)

**v0.0.1 preview.** Score-then-perform. A CLI coding agent — not a VS Code fork.

Vibe coding should not be an unbounded chat plus a pile of tool calls.
That path is already well travelled.

This project joins two existing pieces at the contract, not at the UI:

| Source | What is reused |
|---|---|
| [Japalitynil](https://github.com/japality/japalitynil) | Intent compiled into a **JNL score**: `goal / know / must / never / do / verify`. It can be planned, replayed, and linted. |
| [BeanAlis](https://github.com/japality/beanalis-vscode) | **L0–L3 safety grades.** Grade is decided from the real tool and its arguments. The model cannot promote itself. The desktop rule still holds: *the agent is a servant, never the owner.* |

`jnla` runs on its own. There is no runtime dependency on BeanAlis for VS Code.

---

## Why this is a different idea

A typical vibe agent:

```
while not done:
    thought = llm(chat)
    tool(thought)          # the plan lives in the chat log
```

`jnla`:

```
intent ──compile──► JNL score ──plan──► DAG
                         │
                         ▼
              perform under L0–L3
              must retry / never abort
```

1. **Score first, then perform.** `jnla plan` prints the graph before any file is written.
2. **Constraints are language, not a system prompt.** `never: mentions sudo` goes through the Japalitynil verifier; path escapes go through BeanAlis-style policy. Two layers.
3. **The model cannot grade itself.** A JSON field `"grade": "L0"` does not make `rm -rf` into L0.
4. **The full pipeline runs on the mock provider.** Prove the contract offline, then switch to a real model.

---

## Grades (from BeanAlis, mapped to coding)

| Grade | Allowed | Default |
|---|---|---|
| **L0** | Observe: `list` / `search` | observe |
| **L1** | Read a file | |
| **L2** | Write / patch inside the workspace | **session ceiling** |
| **L3** | Shell, delete, secrets, system paths | requires `--allow-l3` |

YOLO / auto-apply **does not** raise the ceiling and **does not** enable L3. That matches BeanAlis `yoloPolicy`.

---

## Install

The runtime has no third-party dependencies. You need [Japalitynil](https://github.com/japality/japalitynil) as a sibling checkout or an editable install:

```bash
git clone https://github.com/japality/japalitynil.git
git clone https://github.com/japality/jnl-agent.git
pip install -e ./japalitynil
pip install -e ./jnl-agent
jnla --help
```

If `japalitynil` and `jnl-agent` sit next to each other, `python3 -m jnl_agent` also works without an editable install.

---

## Usage

```bash
# Print the score; do not touch the disk
jnla score "add greet()"
jnla plan  "add greet()"

# Offline perform: really add greet() on fixtures/toy
cp -r fixtures/toy /tmp/toy
jnla perform "add a greet(name) helper" --root /tmp/toy --grade L2

# Replay the last run
jnla replay --root /tmp/toy

# Real model, same score
jnla perform "add a greet(name) helper" --root /tmp/toy \
  --provider ollama --model llama3.1

# Observe only
jnla perform "what is in this repo" --grade L0
```

Each `perform` writes `<root>/.jnla/sessions/<utc>/` (score, plan, audit) by default. Pass `--no-record` to skip that.

On `fixtures/toy` the mock does a real `replace` (adds `greet`) and a mechanical `assert`. That shows the pipeline edits code, not just markdown. The mock is not a general engineer; switch to ollama / openai for open-ended vibe coding on the same score.

---

## What a score looks like

Each `do llm` may emit **one** JSON action. `do tool act` grades it, then runs it. There is no while-chat.

```jnl
goal: fulfill the coding intent as a bounded score, not an open chat
know:
  intent = @input
do llm as survey:     # list / search
do tool act as observed:
do llm as inspect:    # read one file
do tool act as focused:
do llm as patch:      # prefer replace (one exact substring)
do tool act as changed:
do llm as check:      # assert path contains …
do tool act as verdict:
return verdict
```

---

## Deliberately not in this repo

- Not a VS Code extension, and not a copy of the BeanAlis webview / inline complete
- Not a generic agent framework
- No multi-model consensus, shadow git, or marketplace at this layer
- No claim that the mock is a general engineer (it only applies the known toy patch)

Those belong to BeanAlis for VS Code. This repo is **score + grade + perform**.

---

## Tests

```bash
pip install -e ../japalitynil
pip install -e ".[dev]"
python -m pytest
```

## License

MIT — Copyright Japality Limited
