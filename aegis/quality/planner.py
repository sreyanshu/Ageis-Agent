"""
Aegis Quality Dimension Planner
Intelligently selects quality validations based on Change Impact, Project Intelligence Graph, and Risk Model.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from aegis.impact.models import ImpactReport
from aegis.planner.models import RiskAssessment, RiskLevel
from aegis.quality.models import QualityDimension


class QualityPlanItem(BaseModel):
    dimension: QualityDimension
    priority: int  # 1-100 (100 highest)
    selection_reason: str
    target_surfaces: List[str] = Field(default_factory=list)
    options: Dict[str, Any] = Field(default_factory=dict)


class QualityPlan(BaseModel):
    plan_id: str
    risk_level: RiskLevel
    selected_dimensions: List[QualityPlanItem] = Field(default_factory=list)
    skipped_dimensions: List[Dict[str, str]] = Field(default_factory=list)
    total_selected: int = 0


class QualityPlanner:
    """Selects and parameterizes quality dimension checks according to risk and blast radius."""

    @classmethod
    def plan(
        cls,
        impact: Optional[ImpactReport] = None,
        risk: Optional[RiskAssessment] = None,
        mode: str = "default",  # "changed-only", "full", "release", "default"
    ) -> QualityPlan:
        risk_lvl = risk.level if risk else RiskLevel.MEDIUM
        selected: List[QualityPlanItem] = []
        skipped: List[Dict[str, str]] = []

        has_ui_changes = False
        has_api_changes = False
        has_auth_or_sec_changes = False

        if impact and impact.has_changes:
            has_ui_changes = len(impact.affected_ui) > 0
            has_api_changes = len(impact.affected_apis) > 0
            has_auth_or_sec_changes = any(
                "auth" in sym.name.lower() or "token" in sym.name.lower() or "sec" in sym.name.lower()
                for sym in impact.changed_symbols
            )

        # Dimension: Security
        if mode in ("full", "release") or has_auth_or_sec_changes or has_api_changes or risk_lvl in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            selected.append(
                QualityPlanItem(
                    dimension=QualityDimension.SECURITY,
                    priority=90 if (has_auth_or_sec_changes or risk_lvl == RiskLevel.CRITICAL) else 70,
                    selection_reason="Selected due to authentication/API changes or high repository risk level.",
                )
            )
        elif mode == "changed-only":
            skipped.append({"dimension": QualityDimension.SECURITY.value, "reason": "No security/API surfaces affected in diff."})
        else:
            selected.append(
                QualityPlanItem(
                    dimension=QualityDimension.SECURITY,
                    priority=50,
                    selection_reason="Standard baseline security scan.",
                )
            )

        # Dimension: Accessibility
        if mode in ("full", "release") or has_ui_changes:
            selected.append(
                QualityPlanItem(
                    dimension=QualityDimension.ACCESSIBILITY,
                    priority=85 if has_ui_changes else 60,
                    selection_reason="Selected due to modified UI components/templates." if has_ui_changes else "Full release accessibility audit.",
                )
            )
        elif mode == "changed-only":
            skipped.append({"dimension": QualityDimension.ACCESSIBILITY.value, "reason": "No UI surfaces impacted by changes."})
        else:
            selected.append(
                QualityPlanItem(
                    dimension=QualityDimension.ACCESSIBILITY,
                    priority=50,
                    selection_reason="Standard baseline accessibility audit.",
                )
            )

        # Dimension: Performance
        if mode in ("full", "release") or has_api_changes or risk_lvl in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            selected.append(
                QualityPlanItem(
                    dimension=QualityDimension.PERFORMANCE,
                    priority=80 if has_api_changes else 60,
                    selection_reason="Selected to verify latency and resource regression on modified endpoints." if has_api_changes else "Baseline performance benchmark.",
                )
            )
        elif mode == "changed-only":
            skipped.append({"dimension": QualityDimension.PERFORMANCE.value, "reason": "No public interfaces or performance-critical code affected."})
        else:
            selected.append(
                QualityPlanItem(
                    dimension=QualityDimension.PERFORMANCE,
                    priority=50,
                    selection_reason="Standard startup and latency measurement.",
                )
            )

        # Dimension: UX
        if mode in ("full", "release") or has_ui_changes:
            selected.append(
                QualityPlanItem(
                    dimension=QualityDimension.UX,
                    priority=75 if has_ui_changes else 50,
                    selection_reason="Selected to validate navigation and interactive controls on modified views." if has_ui_changes else "General UX heuristic evaluation.",
                )
            )
        elif mode == "changed-only":
            skipped.append({"dimension": QualityDimension.UX.value, "reason": "No UI views or journeys modified in change set."})
        else:
            selected.append(
                QualityPlanItem(
                    dimension=QualityDimension.UX,
                    priority=45,
                    selection_reason="Baseline UX heuristic evaluation.",
                )
            )

        return QualityPlan(
            plan_id=f"qplan_{abs(hash(str(selected))) % 100000}",
            risk_level=risk_lvl,
            selected_dimensions=selected,
            skipped_dimensions=skipped,
            total_selected=len(selected),
        )
