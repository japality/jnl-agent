from japalitynil import parse, plan

from jnl_agent.actions import parse_action
from jnl_agent.scores import compile_score


def test_score_is_valid_jnl():
    source = compile_score("add a healthcheck")
    program = parse(source, filename="vibe.jnl")
    compiled = plan(program)
    assert compiled.return_name == "verdict"
    engines = [step.do.engine for step in compiled.steps]
    assert engines == [
        "llm",
        "tool",
        "llm",
        "tool",
        "llm",
        "tool",
        "llm",
        "tool",
    ]
    names = [step.do.name for step in compiled.steps]
    assert names == [
        "survey",
        "observed",
        "inspect",
        "focused",
        "patch",
        "changed",
        "check",
        "verdict",
    ]


def test_parse_action_recovers_json_fence():
    raw = 'Sure.\n```json\n{"op": "list", "path": "."}\n```\n'
    assert parse_action(raw)["op"] == "list"


def test_parse_action_does_not_treat_prose_as_shell():
    action = parse_action("please run sudo rm -rf /")
    assert action["op"] == "note"
