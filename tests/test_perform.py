import shutil
from pathlib import Path

from jnl_agent.cli import main
from jnl_agent.policy import Grade
from jnl_agent.runtime import perform

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "toy"


def test_perform_mock_writes_under_l2(tmp_path):
    (tmp_path / "README.md").write_text("# demo\n", encoding="utf-8")
    result = perform(
        "add a healthcheck note",
        root=tmp_path,
        ceiling=Grade.L2,
        provider="mock",
    )
    assert result.return_value is not None
    writes = [row for row in result.audit if row.get("action") == "write" and row.get("ok")]
    assert writes, result.audit
    written = tmp_path / writes[0]["path"]
    assert written.is_file()
    assert "healthcheck" in written.read_text(encoding="utf-8").lower()


def test_perform_l0_does_not_write(tmp_path):
    result = perform(
        "add a healthcheck note",
        root=tmp_path,
        ceiling=Grade.L0,
        provider="mock",
    )
    writes = [row for row in result.audit if row.get("action") == "write" and row.get("ok")]
    assert writes == []
    denied = [row for row in result.audit if row.get("denied")]
    # mock may emit write JSON; the tool must refuse it
    assert denied or all(row.get("action") != "write" for row in result.audit)
    assert list(tmp_path.glob("*.md")) == []


def test_perform_patches_greeter_fixture(tmp_path):
    shutil.copy(FIXTURE / "greeter.py", tmp_path / "greeter.py")
    result = perform(
        "add a greet(name) helper that returns hello, name!",
        root=tmp_path,
        ceiling=Grade.L2,
        provider="mock",
    )
    replaces = [row for row in result.audit if row.get("action") == "replace" and row.get("ok")]
    assert replaces, result.audit
    text = (tmp_path / "greeter.py").read_text(encoding="utf-8")
    assert "def greet" in text
    assert result.return_value.get("ok") is True
    assert result.return_value.get("action") == "assert"


def test_cli_plan_and_grades(capsys):
    assert main(["grades"]) == 0
    assert "L0" in capsys.readouterr().out
    assert main(["plan", "add a healthcheck"]) == 0
    out = capsys.readouterr().out
    assert "GOAL:" in out
    assert "survey" in out
    assert "inspect" in out
    assert "patch" in out


def test_cli_replay_latest(tmp_path, capsys):
    (tmp_path / "README.md").write_text("# demo\n", encoding="utf-8")
    assert (
        main(
            [
                "perform",
                "add a healthcheck note",
                "--root",
                str(tmp_path),
                "--no-record",
            ]
        )
        == 0
    )
    capsys.readouterr()
    # record on a second run
    assert (
        main(
            [
                "perform",
                "add a healthcheck note",
                "--root",
                str(tmp_path),
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert main(["replay", "--root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "session:" in out
    assert "verdict:" in out
