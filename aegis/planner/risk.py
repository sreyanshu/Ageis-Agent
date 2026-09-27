"""
Aegis Adaptive Risk Engine
Calculates deterministic, explainable risk scores based on change blast radius,
API exposure, data sensitivity, and signature modifications.
"""

from __future__ import annotations
from typing import List

from aegis.impact.models import ImpactReport, SymbolChangeType
from aegis.planner.models import RiskAssessment, RiskLevel, RiskFactor


class AdaptiveRiskEngine:
    """Computes transparent, weighted risk assessments for proposed or detected changes."""

    # Configurable deterministic factor weights (sum to 1.0)
    WEIGHT_MAGNITUDE = 0.20
    WEIGHT_BLAST_RADIUS = 0.25
    WEIGHT_API_EXPOSURE = 0.25
    WEIGHT_DATA_SENSITIVITY = 0.15
    WEIGHT_SIGNATURE_BREAK = 0.15

    def assess_risk(self, impact: ImpactReport) -> RiskAssessment:
        if not impact.has_changes:
            return RiskAssessment(
                level=RiskLevel.LOW,
                composite_score=0.0,
                factors=[
                    RiskFactor(
                        factor_name="change_magnitude",
                        weight=self.WEIGHT_MAGNITUDE,
                        raw_score=0.0,
                        weighted_score=0.0,
                        evidence="No modifications detected in workspace",
                    )
                ],
                reasons=["Zero code or configuration changes detected"],
                recommendation="Targeted sanity verification only",
            )

        factors: List[RiskFactor] = []
        reasons: List[str] = []

        # 1. Change Magnitude Factor
        num_files = len(impact.changed_files)
        num_symbols = len(impact.changed_symbols)
        # Scale: 1 file = 0.2, 5 files = 0.6, 10+ files = 1.0
        magnitude_raw = min(1.0, (num_files * 0.15) + (num_symbols * 0.05))
        factors.append(
            RiskFactor(
                factor_name="change_magnitude",
                weight=self.WEIGHT_MAGNITUDE,
                raw_score=round(magnitude_raw, 3),
                weighted_score=round(self.WEIGHT_MAGNITUDE * magnitude_raw, 3),
                evidence=f"{num_files} changed file(s), {num_symbols} changed symbol(s)",
            )
        )
        if magnitude_raw > 0.5:
            reasons.append(f"High modification volume: {num_files} files changed.")

        # 2. Blast Radius Factor
        blast = impact.blast_radius
        # Scale: 0 = 0.0, 5 dependents = 0.5, 10+ dependents = 1.0
        blast_raw = min(1.0, (blast.direct_count * 0.1) + (blast.indirect_count * 0.05))
        factors.append(
            RiskFactor(
                factor_name="blast_radius",
                weight=self.WEIGHT_BLAST_RADIUS,
                raw_score=round(blast_raw, 3),
                weighted_score=round(self.WEIGHT_BLAST_RADIUS * blast_raw, 3),
                evidence=f"{blast.direct_count} direct dependents, {blast.indirect_count} indirect dependents",
            )
        )
        if blast.total_affected > 5:
            reasons.append(f"Significant downstream blast radius ({blast.total_affected} dependents affected).")

        # 3. API Exposure Factor
        affected_apis = len(impact.affected_apis)
        # Each affected API increases risk by 0.35 up to 1.0
        api_raw = min(1.0, affected_apis * 0.35)
        factors.append(
            RiskFactor(
                factor_name="api_exposure",
                weight=self.WEIGHT_API_EXPOSURE,
                raw_score=round(api_raw, 3),
                weighted_score=round(self.WEIGHT_API_EXPOSURE * api_raw, 3),
                evidence=f"{affected_apis} exposed public API endpoint(s) affected",
            )
        )
        if affected_apis > 0:
            reasons.append(f"Public API contracts impacted ({affected_apis} endpoint(s)).")

        # 4. Data / Database Sensitivity Factor
        affected_db = len(impact.affected_databases)
        db_raw = min(1.0, affected_db * 0.5)
        factors.append(
            RiskFactor(
                factor_name="data_sensitivity",
                weight=self.WEIGHT_DATA_SENSITIVITY,
                raw_score=round(db_raw, 3),
                weighted_score=round(self.WEIGHT_DATA_SENSITIVITY * db_raw, 3),
                evidence=f"{affected_db} database model(s) or table(s) affected",
            )
        )
        if affected_db > 0:
            reasons.append(f"Database schema or entity models altered ({affected_db} model(s)).")

        # 5. Signature Breaking Factor
        sig_changed = sum(1 for s in impact.changed_symbols if s.change_type == SymbolChangeType.SIGNATURE_CHANGED)
        sig_raw = min(1.0, sig_changed * 0.5)
        factors.append(
            RiskFactor(
                factor_name="signature_breaking_risk",
                weight=self.WEIGHT_SIGNATURE_BREAK,
                raw_score=round(sig_raw, 3),
                weighted_score=round(self.WEIGHT_SIGNATURE_BREAK * sig_raw, 3),
                evidence=f"{sig_changed} function or method signature change(s)",
            )
        )
        if sig_changed > 0:
            reasons.append(f"Interface contracts modified ({sig_changed} signature change(s)).")

        # Aggregate composite risk score
        composite_score = sum(f.weighted_score for f in factors)
        composite_score = min(1.0, max(0.0, round(composite_score, 3)))

        # Categorize
        if composite_score >= 0.75:
            level = RiskLevel.CRITICAL
            recommendation = "Full regression test suite and integration validation mandatory"
        elif composite_score >= 0.45:
            level = RiskLevel.HIGH
            recommendation = "Targeted tests + downstream integration validation required"
        elif composite_score >= 0.20:
            level = RiskLevel.MEDIUM
            recommendation = "Targeted tests for affected symbols and direct dependents"
        else:
            level = RiskLevel.LOW
            recommendation = "Targeted unit tests only"

        if not reasons:
            reasons.append("Low complexity isolated modification")

        return RiskAssessment(
            level=level,
            composite_score=composite_score,
            factors=factors,
            reasons=reasons,
            recommendation=recommendation,
        )
