"""
Unit Tests for Aegis Security Engine & SARIF Ingestion
"""

import json
from pathlib import Path
from aegis.runners.base import ExecutionContext, RunnerCategory
from aegis.quality.security.sarif import SARIFParser
from aegis.quality.security.runner import SecurityRunner
from aegis.quality.security.adapter import SARIFSecurityAdapter
from aegis.quality.models import (
    QualityDimension,
    QualityStatus,
    FindingSeverity,
    QualityBaseline,
    BaselineStatus,
    Waiver,
)


def test_sarif_parser_valid_v2_1_0(tmp_path: Path):
    sarif_data = {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "semgrep",
                        "version": "1.34.0",
                        "rules": [
                            {
                                "id": "python.jwt-none-algorithm",
                                "shortDescription": {"text": "Insecure JWT verification with algorithm 'none'"},
                                "helpUri": "https://semgrep.dev/r/python.jwt-none-algorithm",
                                "properties": {"security-severity": "9.5"},
                            }
                        ],
                    }
                },
                "results": [
                    {
                        "ruleId": "python.jwt-none-algorithm",
                        "level": "error",
                        "message": {"text": "jwt.decode without algorithms parameter allows algorithm 'none'"},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": "backend/auth.py"},
                                    "region": {"startLine": 88, "startColumn": 10, "snippet": {"text": "jwt.decode(token, key)"}},
                                }
                            }
                        ],
                    }
                ],
            }
        ],
    }
    sarif_file = tmp_path / "semgrep.sarif"
    sarif_file.write_text(json.dumps(sarif_data))

    findings, evidence = SARIFParser.parse_sarif_file(str(sarif_file))
    assert len(findings) == 1
    assert len(evidence) == 1

    f = findings[0]
    assert f.dimension == QualityDimension.SECURITY
    assert f.severity == FindingSeverity.CRITICAL  # Score 9.5 mapped to CRITICAL
    assert f.provenance["scanner"] == "semgrep"
    assert f.provenance["file_path"] == "backend/auth.py"
    assert f.provenance["line_start"] == 88
    assert f.fingerprint.startswith("qf_sec_")


def test_sarif_parser_malformed_input_safety(tmp_path: Path):
    # Missing runs list
    bad_sarif = {"version": "2.1.0"}
    try:
        SARIFParser.parse_sarif_dict(bad_sarif)
        assert False, "Should raise ValueError for malformed SARIF"
    except ValueError as e:
        assert "runs" in str(e)


def test_security_runner_unavailable_when_no_reports(tmp_path: Path):
    runner = SecurityRunner(tmp_path)
    ctx = ExecutionContext(
        workspace_root=str(tmp_path),
        category=RunnerCategory.SECURITY,
        dry_run=False,
        options={"simulate": False},
    )
    res = runner.execute(ctx)
    # MUST be UNAVAILABLE, never PASS!
    assert res.status == QualityStatus.UNAVAILABLE
    assert "No SARIF reports" in (res.error_message or "")


def test_security_runner_ingests_real_sarif_file(tmp_path: Path):
    sec_dir = tmp_path / ".aegis" / "security"
    sec_dir.mkdir(parents=True, exist_ok=True)
    
    sarif_data = {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "bandit", "version": "1.7.0"}},
                "results": [
                    {
                        "ruleId": "B101",
                        "level": "warning",
                        "message": {"text": "Use of assert detected"},
                        "locations": [{"physicalLocation": {"artifactLocation": {"uri": "main.py"}, "region": {"startLine": 10}}}],
                    }
                ],
            }
        ],
    }
    (sec_dir / "bandit.sarif").write_text(json.dumps(sarif_data))

    runner = SecurityRunner(tmp_path)
    ctx = ExecutionContext(
        workspace_root=str(tmp_path),
        category=RunnerCategory.SECURITY,
        dry_run=False,
    )
    res = runner.execute(ctx)
    assert res.status in (QualityStatus.WARN, QualityStatus.PASS)
    assert len(res.findings) == 1
    assert res.findings[0].severity == FindingSeverity.MEDIUM
