"""
Aegis SARIF Parser & Finding Normalizer
Robust ingestion of standard SARIF v2.1.0 reports (Bandit, Semgrep, Trivy, CodeQL, etc.)
"""

from __future__ import annotations
import json
import hashlib
from typing import Dict, Any, List, Optional, Tuple

from aegis.quality.models import (
    QualityDimension,
    QualityFinding,
    QualityEvidence,
    FindingSeverity,
    EvidenceKind,
)


class SARIFParser:
    """Robust parser for SARIF v2.1.0 reports with safe fallback for malformed documents."""

    @staticmethod
    def normalize_level(level: Optional[str], score: Optional[float] = None) -> FindingSeverity:
        if score is not None:
            if score >= 9.0:
                return FindingSeverity.CRITICAL
            elif score >= 7.0:
                return FindingSeverity.HIGH
            elif score >= 4.0:
                return FindingSeverity.MEDIUM
            else:
                return FindingSeverity.LOW

        lvl = (level or "").lower()
        if lvl == "error":
            return FindingSeverity.HIGH
        elif lvl == "warning":
            return FindingSeverity.MEDIUM
        elif lvl in ("note", "info"):
            return FindingSeverity.LOW
        return FindingSeverity.INFO

    @classmethod
    def parse_sarif_dict(
        cls, sarif_dict: Dict[str, Any], source_label: str = "sarif"
    ) -> Tuple[List[QualityFinding], List[QualityEvidence]]:
        """Parses a dictionary conforming to SARIF 2.1.0 into standardized Aegis QualityFindings."""
        findings: List[QualityFinding] = []
        evidence_list: List[QualityEvidence] = []

        if not isinstance(sarif_dict, dict):
            raise ValueError("SARIF document must be a JSON object.")

        if "runs" not in sarif_dict or not isinstance(sarif_dict["runs"], list):
            raise ValueError("Malformed SARIF: 'runs' must be a list.")

        runs = sarif_dict["runs"]

        for run_idx, run in enumerate(runs):
            if not isinstance(run, dict):
                continue

            tool_info = run.get("tool", {}).get("driver", {})
            scanner_name = tool_info.get("name", "unknown_scanner")
            scanner_version = tool_info.get("version", "1.0.0")

            rules_map: Dict[str, Dict[str, Any]] = {}
            for r in tool_info.get("rules", []):
                if isinstance(r, dict) and "id" in r:
                    rules_map[r["id"]] = r

            results = run.get("results", [])
            for res_idx, res in enumerate(results):
                if not isinstance(res, dict):
                    continue

                rule_id = res.get("ruleId", "unknown_rule")
                rule_meta = rules_map.get(rule_id, {})
                rule_desc = rule_meta.get("fullDescription", {}).get("text", rule_meta.get("shortDescription", {}).get("text", ""))
                help_uri = rule_meta.get("helpUri", "")

                # Extract score from properties
                sec_score: Optional[float] = None
                props = rule_meta.get("properties", {}) or res.get("properties", {})
                if "security-severity" in props:
                    try:
                        sec_score = float(props["security-severity"])
                    except (ValueError, TypeError):
                        pass

                raw_level = res.get("level", "warning")
                sev = cls.normalize_level(raw_level, sec_score)

                msg = res.get("message", {}).get("text", "Security issue detected")
                
                # Locations
                locations = res.get("locations", [{}])
                loc = locations[0] if locations else {}
                phys_loc = loc.get("physicalLocation", {})
                artifact_loc = phys_loc.get("artifactLocation", {})
                file_path = artifact_loc.get("uri", "unknown_file")
                region = phys_loc.get("region", {})
                line_start = region.get("startLine", 1)
                col_start = region.get("startColumn", 1)
                snippet = region.get("snippet", {}).get("text", "")

                affected_target = f"{file_path}:{line_start}"

                # Deterministic fingerprint
                raw_fp_seed = f"security:{scanner_name}:{rule_id}:{file_path}:{line_start}"
                fingerprint = f"qf_sec_{hashlib.sha256(raw_fp_seed.encode('utf-8')).hexdigest()[:16]}"

                ev_id = f"ev_sarif_{run_idx}_{res_idx}"
                evidence_item = QualityEvidence(
                    evidence_id=ev_id,
                    kind=EvidenceKind.SCANNED,
                    description=msg,
                    raw_data={
                        "scanner": scanner_name,
                        "scanner_version": scanner_version,
                        "rule_id": rule_id,
                        "raw_level": raw_level,
                        "snippet": snippet,
                    },
                    provenance={
                        "scanner": scanner_name,
                        "scanner_version": scanner_version,
                        "rule_id": rule_id,
                        "file_path": file_path,
                        "line_start": line_start,
                        "col_start": col_start,
                        "help_uri": help_uri,
                    },
                )
                evidence_list.append(evidence_item)

                finding = QualityFinding(
                    finding_id=f"sec_{rule_id}_{abs(hash(affected_target)) % 10000}",
                    dimension=QualityDimension.SECURITY,
                    severity=sev,
                    category="security",
                    title=f"Security: {rule_id}",
                    description=msg if not rule_desc else f"{msg} — {rule_desc}",
                    affected_target=affected_target,
                    evidence=[evidence_item],
                    provenance={
                        "scanner": scanner_name,
                        "scanner_version": scanner_version,
                        "rule_id": rule_id,
                        "file_path": file_path,
                        "line_start": line_start,
                        "col_start": col_start,
                        "help_uri": help_uri,
                    },
                    confidence=1.0,
                    remediation_reference=help_uri,
                    fingerprint=fingerprint,
                )
                findings.append(finding)

        return findings, evidence_list

    @classmethod
    def parse_sarif_file(cls, file_path: str) -> Tuple[List[QualityFinding], List[QualityEvidence]]:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.parse_sarif_dict(data, source_label=file_path)
