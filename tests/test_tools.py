from jnl_agent.policy import Grade, Policy
from jnl_agent.tools import Workspace


def test_replace_exactly_one(tmp_path):
    path = tmp_path / "greeter.py"
    path.write_text("def hello(name):\n    return f\"hi {name}\"\n", encoding="utf-8")
    ws = Workspace(Policy(root=tmp_path, ceiling=Grade.L2))
    result = ws.replace(
        "greeter.py",
        "def hello(name):\n    return f\"hi {name}\"\n",
        "def hello(name):\n    return f\"hi {name}\"\n\n\ndef greet(name):\n    return f\"hello, {name}!\"\n",
    )
    assert result["ok"] is True
    assert "def greet" in path.read_text(encoding="utf-8")


def test_replace_rejects_ambiguous(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\nx = 1\n", encoding="utf-8")
    ws = Workspace(Policy(root=tmp_path, ceiling=Grade.L2))
    result = ws.replace("a.py", "x = 1\n", "y = 2\n")
    assert result["ok"] is False
    assert "2 times" in result["error"]


def test_assert_contains(tmp_path):
    (tmp_path / "a.py").write_text("def greet():\n    pass\n", encoding="utf-8")
    ws = Workspace(Policy(root=tmp_path, ceiling=Grade.L0))
    assert ws.assert_file("a.py", contains="def greet")["ok"] is True
    assert ws.assert_file("a.py", contains="def missing")["ok"] is False
