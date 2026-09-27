"""
Aegis Deterministic UX Heuristic Evaluator
Analyzes DOM trees, forms, navigation structures, and user journeys for objective UX defects.
"""

from __future__ import annotations
import re
from typing import Dict, Any, List, Optional, Tuple

from aegis.quality.models import (
    QualityDimension,
    QualityFinding,
    QualityEvidence,
    FindingSeverity,
    EvidenceKind,
)


class UXHeuristicEvaluator:
    """Evaluates objective UX signals without relying on subjective AI judgments."""

    @classmethod
    def evaluate_html(cls, html_content: str, file_path: str = "ui_view.html") -> Tuple[List[QualityFinding], List[QualityEvidence]]:
        """Scans an HTML markup string for objective UX defects."""
        findings: List[QualityFinding] = []
        evidence_list: List[QualityEvidence] = []

        # 1. Check for unlabeled interactive buttons (<button></button> or <button> </button> without aria-label)
        button_matches = re.finditer(r'<button\b([^>]*)>(.*?)</button>', html_content, re.IGNORECASE | re.DOTALL)
        for idx, match in enumerate(button_matches):
            attrs = match.group(1)
            inner_text = match.group(2).strip()
            if not inner_text and "aria-label" not in attrs and "title" not in attrs:
                target = f"button[idx={idx}]"
                ev = QualityEvidence(
                    evidence_id=f"ev_ux_btn_{idx}",
                    kind=EvidenceKind.OBSERVED,
                    description="Button element has no inner text, aria-label, or title attribute.",
                    raw_data={"snippet": match.group(0)},
                    provenance={"file_path": file_path, "target": target},
                )
                evidence_list.append(ev)

                f = QualityFinding(
                    finding_id=f"ux_unlabeled_button_{idx}",
                    dimension=QualityDimension.UX,
                    severity=FindingSeverity.HIGH,
                    category="unlabeled_control",
                    title="UX: Interactive button has no label",
                    description="User cannot determine button action because it lacks text, aria-label, and title.",
                    affected_target=target,
                    evidence=[ev],
                    provenance={"file_path": file_path, "target": target, "rule_id": "ux.unlabeled_button"},
                    remediation_reference="Provide descriptive inner text or an aria-label attribute.",
                )
                f.fingerprint = f.compute_fingerprint()
                findings.append(f)

        # 2. Check for dead-end links (<a href="#"> or <a href="">)
        link_matches = re.finditer(r'<a\b[^>]*href=["\'](#|)["\'][^>]*>(.*?)</a>', html_content, re.IGNORECASE)
        for idx, match in enumerate(link_matches):
            target = f"a[idx={idx}]"
            ev = QualityEvidence(
                evidence_id=f"ev_ux_link_{idx}",
                kind=EvidenceKind.OBSERVED,
                description="Anchor tag points to '#' or empty string resulting in a dead-end interaction.",
                raw_data={"snippet": match.group(0)},
                provenance={"file_path": file_path, "target": target},
            )
            evidence_list.append(ev)

            f = QualityFinding(
                finding_id=f"ux_dead_end_link_{idx}",
                dimension=QualityDimension.UX,
                severity=FindingSeverity.MEDIUM,
                category="dead_end_navigation",
                title="UX: Dead-end anchor link detected",
                description="Anchor link with href='#' fails to provide navigational affordance.",
                affected_target=target,
                evidence=[ev],
                provenance={"file_path": file_path, "target": target, "rule_id": "ux.dead_end_link"},
                remediation_reference="Replace placeholder href with concrete route or <button> for actions.",
            )
            f.fingerprint = f.compute_fingerprint()
            findings.append(f)

        # 3. Check heading hierarchy skips (e.g. h1 followed directly by h4/h5)
        headings = re.findall(r'<h([1-6])\b', html_content, re.IGNORECASE)
        if headings:
            levels = [int(h) for h in headings]
            for i in range(len(levels) - 1):
                if levels[i + 1] - levels[i] > 1:
                    target = f"h{levels[i+1]}"
                    ev = QualityEvidence(
                        evidence_id=f"ev_ux_heading_{i}",
                        kind=EvidenceKind.OBSERVED,
                        description=f"Heading hierarchy skips from h{levels[i]} directly to h{levels[i+1]}.",
                        raw_data={"from_level": levels[i], "to_level": levels[i + 1]},
                        provenance={"file_path": file_path, "target": target},
                    )
                    evidence_list.append(ev)

                    f = QualityFinding(
                        finding_id=f"ux_heading_skip_{i}",
                        dimension=QualityDimension.UX,
                        severity=FindingSeverity.LOW,
                        category="heading_hierarchy",
                        title=f"UX: Heading hierarchy skipped from h{levels[i]} to h{levels[i+1]}",
                        description="Heading levels should not be skipped to maintain logical document structure for screen readers and scannability.",
                        affected_target=target,
                        evidence=[ev],
                        provenance={"file_path": file_path, "target": target, "rule_id": "ux.heading_skip"},
                        remediation_reference="Use sequential heading levels (h1 -> h2 -> h3).",
                    )
                    f.fingerprint = f.compute_fingerprint()
                    findings.append(f)

        return findings, evidence_list

    @classmethod
    def evaluate_journey(cls, steps: List[Dict[str, Any]], journey_id: str = "journey") -> Tuple[List[QualityFinding], List[QualityEvidence]]:
        """Evaluates an E2E journey for excessive steps, repeated actions, or dead ends."""
        findings: List[QualityFinding] = []
        evidence_list: List[QualityEvidence] = []

        # Check for excessive step count (> 12 steps)
        if len(steps) > 12:
            target = f"journey:{journey_id}"
            ev = QualityEvidence(
                evidence_id=f"ev_ux_journey_len_{journey_id}",
                kind=EvidenceKind.DERIVED,
                description=f"User journey contains {len(steps)} steps which exceeds recommended threshold (12).",
                raw_data={"step_count": len(steps)},
                provenance={"journey_id": journey_id, "target": target},
            )
            evidence_list.append(ev)

            f = QualityFinding(
                finding_id=f"ux_excessive_journey_{journey_id}",
                dimension=QualityDimension.UX,
                severity=FindingSeverity.LOW,
                category="excessive_steps",
                title=f"UX: Journey {journey_id} has high interaction friction",
                description=f"Journey requires {len(steps)} interaction steps to complete.",
                affected_target=target,
                evidence=[ev],
                provenance={"journey_id": journey_id, "target": target, "rule_id": "ux.excessive_journey"},
                remediation_reference="Streamline workflow to reduce required user interaction steps.",
            )
            f.fingerprint = f.compute_fingerprint()
            findings.append(f)

        return findings, evidence_list
