"""
Aegis Security Scanner Adapters (SARIF file ingestion, external scanners, simulation)
"""

from __future__ import annotations
import glob
from pathlib import Path
from abc import abstractmethod
from typing import Dict, Any, List, Optional, Tuple

from aegis.quality.base import QualityAdapter
from aegis.quality.models import QualityFinding, QualityEvidence
from aegis.quality.security.sarif import SARIFParser


class SecurityAdapter(QualityAdapter):
    """Abstract security scanner adapter."""

    @abstractmethod
    def ingest_findings(self, options: Optional[Dict[str, Any]] = None) -> Tuple[List[QualityFinding], List[QualityEvidence]]:
        pass


class SARIFSecurityAdapter(SecurityAdapter):
    """Ingests SARIF reports from project or .aegis/security/ directory."""

    def __init__(self, workspace_root: Path | str) -> None:
        self.workspace_root = Path(workspace_root).resolve()

    @property
    def adapter_name(self) -> str:
        return "sarif-ingestion"

    def is_available(self) -> bool:
        # Returns True if any SARIF files exist in workspace or .aegis/security/
        return len(self._find_sarif_files()) > 0

    def _find_sarif_files(self) -> List[str]:
        patterns = [
            str(self.workspace_root / ".aegis" / "security" / "*.sarif"),
            str(self.workspace_root / "*.sarif"),
            str(self.workspace_root / "reports" / "*.sarif"),
        ]
        files: List[str] = []
        for pat in patterns:
            files.extend(glob.glob(pat))
        return sorted(list(set(files)))

    def ingest_findings(self, options: Optional[Dict[str, Any]] = None) -> Tuple[List[QualityFinding], List[QualityEvidence]]:
        opts = options or {}
        explicit_file = opts.get("sarif_file")
        files = [explicit_file] if explicit_file else self._find_sarif_files()

        if not files:
            raise FileNotFoundError("No SARIF security reports found in workspace.")

        all_findings: List[QualityFinding] = []
        all_evidence: List[QualityEvidence] = []

        for f in files:
            findings, ev = SARIFParser.parse_sarif_file(f)
            all_findings.extend(findings)
            all_evidence.extend(ev)

        return all_findings, all_evidence


class SimulatedSecurityAdapter(SecurityAdapter):
    """Deterministic simulated security scanner for testing."""

    @property
    def adapter_name(self) -> str:
        return "simulated-security"

    def is_available(self) -> bool:
        return True

    def ingest_findings(self, options: Optional[Dict[str, Any]] = None) -> Tuple[List[QualityFinding], List[QualityEvidence]]:
        opts = options or {}
        if opts.get("clean_pass", False):
            return [], []

        sample_sarif = {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "bandit",
                            "version": "1.7.5",
                            "rules": [
                                {
                                    "id": "B105",
                                    "shortDescription": {"text": "Hardcoded password string detected in source"},
                                    "helpUri": "https://bandit.readthedocs.io/en/latest/plugins/b105_hardcoded_password_string.html",
                                    "properties": {"security-severity": "8.5"},
                                }
                            ],
                        }
                    },
                    "results": [
                        {
                            "ruleId": "B105",
                            "level": "error",
                            "message": {"text": "Possible hardcoded password 'secret_pass_123'"},
                            "locations": [
                                {
                                    "physicalLocation": {
                                        "artifactLocation": {"uri": "app/auth/routes.py"},
                                        "region": {"startLine": 42, "startColumn": 12, "snippet": {"text": "password = 'secret_pass_123'"}},
                                    }
                                }
                            ],
                        }
                    ],
                }
            ],
        }
        return SARIFParser.parse_sarif_dict(sample_sarif)
