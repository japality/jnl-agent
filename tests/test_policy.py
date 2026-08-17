from jnl_agent.policy import Grade, Policy, PolicyDenied, grade_action, parse_grade


def test_observe_is_l0():
    assert grade_action({"op": "list", "path": "."}) is Grade.L0
    assert grade_action({"op": "search", "query": "foo"}) is Grade.L0


def test_read_is_l1():
    assert grade_action({"op": "read", "path": "src/main.py"}) is Grade.L1


def test_write_is_l2():
    assert grade_action({"op": "write", "path": "src/main.py", "content": "x"}) is Grade.L2
    assert grade_action({"op": "replace", "path": "src/main.py", "old": "a", "new": "b"}) is Grade.L2


def test_assert_is_l0():
    assert grade_action({"op": "assert", "path": "src/main.py", "contains": "def greet"}) is Grade.L0


def test_shell_and_secrets_are_l3():
    assert grade_action({"op": "run", "cmd": "pytest -q"}) is Grade.L3
    assert grade_action({"op": "write", "path": ".env", "content": "k=v"}) is Grade.L3
    assert grade_action({"op": "read", "path": ".ssh/id_rsa"}) is Grade.L3


def test_model_cannot_self_grade():
    action = {"op": "run", "cmd": "rm -rf /", "grade": "L0", "readOnlyHint": True}
    assert grade_action(action) is Grade.L3


def test_ceiling_blocks_write(tmp_path):
    policy = Policy(root=tmp_path, ceiling=Grade.L0)
    try:
        policy.enforce({"op": "write", "path": "x.txt", "content": "n"})
    except PolicyDenied as exc:
        assert "L2" in str(exc)
    else:
        raise AssertionError("expected PolicyDenied")


def test_confine_rejects_escape(tmp_path):
    policy = Policy(root=tmp_path, ceiling=Grade.L2)
    try:
        policy.confine("../outside.txt")
    except PolicyDenied:
        return
    raise AssertionError("expected escape to be denied")


def test_parse_grade():
    assert parse_grade("l2") is Grade.L2
    assert parse_grade("3") is Grade.L3
