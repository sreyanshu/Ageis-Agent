"""
CLI Integration Tests for Aegis Phase 5 Historical Intelligence Commands
"""

import json
from pathlib import Path
from aegis.cli.main import main


def test_cli_history_and_analyze_commands(tmp_path: Path, capsys):
    # 1. Initialize workspace
    main(["--workspace", str(tmp_path), "init"])
    capsys.readouterr()

    # 2. Run dry-run test to populate initial history
    main(["--workspace", str(tmp_path), "test", "--dry-run"])
    capsys.readouterr()

    # 3. aegis history --json
    code = main(["--workspace", str(tmp_path), "--json", "history"])
    assert code == 0
    out = capsys.readouterr().out
    history_records = json.loads(out)
    assert isinstance(history_records, list)
    assert len(history_records) > 0

    # 4. aegis history flaky --json
    code = main(["--workspace", str(tmp_path), "--json", "history", "flaky"])
    assert code == 0
    out = capsys.readouterr().out
    flaky_records = json.loads(out)
    assert isinstance(flaky_records, dict)

    # 5. aegis analyze effectiveness --json
    code = main(["--workspace", str(tmp_path), "--json", "analyze", "effectiveness"])
    assert code == 0
    out = capsys.readouterr().out
    eff_records = json.loads(out)
    assert isinstance(eff_records, dict)

    # 6. aegis analyze redundancy --json
    code = main(["--workspace", str(tmp_path), "--json", "analyze", "redundancy"])
    assert code == 0
    out = capsys.readouterr().out
    assert isinstance(json.loads(out), list)

    # 7. aegis analyze risk --json
    code = main(["--workspace", str(tmp_path), "--json", "analyze", "risk"])
    assert code == 0
    out = capsys.readouterr().out
    risk_calib = json.loads(out)
    assert "current_predicted_risk" in risk_calib

    # 8. aegis history failures --json
    code = main(["--workspace", str(tmp_path), "--json", "history", "failures"])
    assert code == 0
    out = capsys.readouterr().out
    assert isinstance(json.loads(out), list)

    # 9. aegis history quality --json
    code = main(["--workspace", str(tmp_path), "--json", "history", "quality"])
    assert code == 0
    out = capsys.readouterr().out
    assert isinstance(json.loads(out), list)

    # 10. aegis plan --explain --json
    code = main(["--workspace", str(tmp_path), "--json", "plan", "--explain"])
    assert code == 0
    out = capsys.readouterr().out
    plan_data = json.loads(out)
    assert "explanations" in plan_data
    assert len(plan_data["explanations"]) > 0
