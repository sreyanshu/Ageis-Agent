"""
CLI Integration Tests for Aegis Phase 4 Quality Commands
"""

import json
from pathlib import Path
from aegis.cli.main import main


def test_cli_quality_commands(tmp_path: Path, capsys):
    # Initialize workspace
    main(["--workspace", str(tmp_path), "init"])
    capsys.readouterr()

    # 1. aegis quality --dry-run --json
    code = main(["--workspace", str(tmp_path), "--json", "quality", "--dry-run"])
    assert code == 0
    out = capsys.readouterr().out
    results = json.loads(out)
    assert "accessibility" in results
    assert "security" in results
    assert "performance" in results
    assert "ux" in results

    # 2. aegis quality accessibility --dry-run
    code = main(["--workspace", str(tmp_path), "--json", "quality", "accessibility", "--dry-run"])
    assert code == 0
    out = capsys.readouterr().out
    res_a11y = json.loads(out)
    assert "accessibility" in res_a11y

    # 3. aegis quality performance --dry-run
    code = main(["--workspace", str(tmp_path), "--json", "quality", "performance", "--dry-run"])
    assert code == 0
    out = capsys.readouterr().out
    res_perf = json.loads(out)
    assert "performance" in res_perf
