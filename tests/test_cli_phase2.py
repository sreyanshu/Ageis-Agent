import json
from pathlib import Path
from aegis.cli.main import main


def test_cli_graph_and_risk(tmp_path: Path, capsys):
    # 1. Initialize
    main(["--workspace", str(tmp_path), "init"])
    capsys.readouterr()

    # Create python file
    (tmp_path / "calc.py").write_text("def add(a: int, b: int) -> int:\n    return a + b\n")

    # 2. Graph build
    code = main(["--workspace", str(tmp_path), "--json", "graph", "build"])
    assert code == 0
    out = capsys.readouterr().out
    stats = json.loads(out)
    assert stats["total_nodes"] >= 2

    # 3. Graph inspect
    code = main(["--workspace", str(tmp_path), "--json", "graph", "inspect", "python:calc.add"])
    assert code == 0
    out = capsys.readouterr().out
    node = json.loads(out)
    assert node["name"] == "add"

    # 4. Risk command
    code = main(["--workspace", str(tmp_path), "--json", "risk"])
    assert code == 0
    out = capsys.readouterr().out
    risk = json.loads(out)
    assert "level" in risk
    assert "composite_score" in risk

    # 5. Plan command
    code = main(["--workspace", str(tmp_path), "--json", "plan"])
    assert code == 0
    out = capsys.readouterr().out
    plan = json.loads(out)
    assert "risk_level" in plan
    assert "selected_tests" in plan
