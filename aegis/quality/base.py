"""
Aegis Quality Runner & Adapter Abstract Base Classes
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from aegis.runners.base import ExecutionContext
from aegis.quality.models import (
    QualityDimension,
    QualityCapability,
    QualityResult,
    QualityFinding,
    QualityBaseline,
    QualityStatus,
    BaselineStatus,
    Waiver,
    FindingSeverity,
)


class QualityAdapter(ABC):
    """Abstract adapter connecting external quality engines (e.g. axe-core, SARIF, Lighthouse)."""

    @property
    @abstractmethod
    def adapter_name(self) -> str:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Determines if the external tool/runtime is installed and available."""
        pass


class QualityRunner(ABC):
    """Abstract base class for all Quality Dimension runners (Accessibility, Security, Performance, UX)."""

    def __init__(self, workspace_root: Path | str) -> None:
        self.workspace_root = Path(workspace_root).resolve()

    @property
    @abstractmethod
    def dimension(self) -> QualityDimension:
        pass

    @property
    @abstractmethod
    def capability(self) -> QualityCapability:
        pass

    @abstractmethod
    def supports(self, context: ExecutionContext) -> bool:
        pass

    @abstractmethod
    def execute(self, context: ExecutionContext) -> QualityResult:
        pass

    def evaluate_baseline(
        self,
        current_findings: List[QualityFinding],
        baseline: Optional[QualityBaseline],
        waivers: Optional[List[Waiver]] = None,
    ) -> Tuple[List[QualityFinding], Dict[str, Any]]:
        """
        Classifies findings against a historical baseline and active waivers.
        Returns updated findings and comparison summary statistics.
        """
        waivers = waivers or []
        active_waivers = {w.finding_fingerprint: w for w in waivers if not w.is_expired()}
        baseline_fingerprints = set(baseline.findings_fingerprints) if baseline else set()

        classified_findings: List[QualityFinding] = []
        new_count = 0
        regressed_count = 0
        existing_count = 0
        waived_count = 0

        for finding in current_findings:
            if not finding.fingerprint:
                finding.fingerprint = finding.compute_fingerprint()

            fp = finding.fingerprint
            if fp in active_waivers:
                finding.baseline_status = BaselineStatus.WAIVED
                finding.metadata["waiver_reason"] = active_waivers[fp].reason
                finding.metadata["waiver_owner"] = active_waivers[fp].owner
                waived_count += 1
            elif fp in baseline_fingerprints:
                finding.baseline_status = BaselineStatus.EXISTING
                existing_count += 1
            else:
                if finding.severity in (FindingSeverity.CRITICAL, FindingSeverity.HIGH):
                    finding.baseline_status = BaselineStatus.REGRESSED
                    regressed_count += 1
                else:
                    finding.baseline_status = BaselineStatus.NEW
                    new_count += 1

            classified_findings.append(finding)

        # Check for resolved findings
        current_fps = {f.fingerprint for f in classified_findings}
        resolved_count = len(baseline_fingerprints - current_fps)

        summary = {
            "baseline_present": baseline is not None,
            "total_findings": len(classified_findings),
            "new_count": new_count,
            "regressed_count": regressed_count,
            "existing_count": existing_count,
            "waived_count": waived_count,
            "resolved_count": resolved_count,
        }

        return classified_findings, summary
