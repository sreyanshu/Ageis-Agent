import json
from pathlib import Path
from aegis.cli.main import main


def test_cli_init_and_discover(tmp_path: Path, capsys):
    # Test aegis init --json
    code = main(["--workspace", str(tmp_path), "--json", "init"])
    assert code == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["status"] == "initialized"

    # Test aegis discover --json
    code = main(["--workspace", str(tmp_path), "--json", "discover"])
    assert code == 0
    out = capsys.readouterr().out
    profile = json.loads(out)
    assert "project_name" in profile
    assert "tree_hash" in profile


def test_cli_impact_and_plan(tmp_path: Path, capsys):
    main(["--workspace", str(tmp_path), "init"])
    capsys.readouterr()

    # Add a file
    (tmp_path / "new_module.py").write_text("def hello(): pass")

    # Impact
    code = main(["--workspace", str(tmp_path), "--json", "impact"])
    assert code == 0
    out = capsys.readouterr().out
    changes = json.loads(out)
    assert "new_module.py" in changes["changed_files"]
    assert changes["has_changes"] is True

    # Plan
    code = main(["--workspace", str(tmp_path), "--json", "plan"])
    assert code == 0
    out = capsys.readouterr().out
    plan = json.loads(out)
    assert "risk_level" in plan
    assert plan["total_planned"] >= 1


def test_cli_test_and_release_check(tmp_path: Path, capsys):
    code = main(["--workspace", str(tmp_path), "--json", "test", "--dry-run"])
    assert code == 0
    out = capsys.readouterr().out
    report = json.loads(out)
    assert report["total_tests"] >= 1
    assert "release_assessment" in report

    # Release check
    code = main(["--workspace", str(tmp_path), "--json", "release-check"])
    assert code == 0
    out = capsys.readouterr().out
    assessment = json.loads(out)
    assert "verdict" in assessment
