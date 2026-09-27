import json
from pathlib import Path
from aegis.cli.main import main


def test_cli_execution_commands(tmp_path: Path, capsys):
    # Initialize workspace
    main(["--workspace", str(tmp_path), "init"])
    capsys.readouterr()

    # 1. aegis test --dry-run
    code = main(["--workspace", str(tmp_path), "--json", "test", "--dry-run"])
    assert code == 0
    out = capsys.readouterr().out
    report = json.loads(out)
    assert report["total_tests"] >= 1
    assert "release_assessment" in report

    # 2. aegis test sanity --json
    code = main(["--workspace", str(tmp_path), "--json", "test", "sanity"])
    assert code == 0
    out = capsys.readouterr().out
    report = json.loads(out)
    assert any(r["category"] == "sanity" for r in report["test_results"])

    # 3. aegis run --json (full DAG)
    code = main(["--workspace", str(tmp_path), "--json", "run", "--dry-run"])
    assert code == 0
    out = capsys.readouterr().out
    report = json.loads(out)
    assert report["passed"] >= 1
