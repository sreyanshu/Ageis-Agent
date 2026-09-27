from aegis.impact.models import (
    ImpactReport,
    ChangedSymbol,
    SymbolChangeType,
    AffectedEntity,
    BlastRadius,
)
from aegis.planner.risk import AdaptiveRiskEngine
from aegis.planner.models import RiskLevel


def test_risk_engine_clean_state():
    engine = AdaptiveRiskEngine()
    impact = ImpactReport(
        report_id="imp_1",
        tree_hash="hash1",
        has_changes=False,
    )
    risk = engine.assess_risk(impact)
    assert risk.level == RiskLevel.LOW
    assert risk.composite_score == 0.0


def test_risk_engine_critical_change():
    engine = AdaptiveRiskEngine()
    impact = ImpactReport(
        report_id="imp_2",
        tree_hash="hash2",
        has_changes=True,
        changed_files=["app/auth.py", "app/routes.py", "app/models.py", "app/db.py"],
        changed_symbols=[
            ChangedSymbol(
                symbol_id="py:auth.login",
                name="login",
                change_type=SymbolChangeType.SIGNATURE_CHANGED,
                symbol_type="function",
                file_path="app/auth.py",
            )
        ],
        affected_apis=[
            AffectedEntity(id="api:POST:/login", name="POST /login", entity_type="route", file_path="app/routes.py"),
            AffectedEntity(id="api:POST:/register", name="POST /register", entity_type="route", file_path="app/routes.py"),
        ],
        affected_databases=[
            AffectedEntity(id="db:User", name="User", entity_type="db_model", file_path="app/models.py"),
        ],
        blast_radius=BlastRadius(direct_count=6, indirect_count=12, total_affected=18),
    )

    risk = engine.assess_risk(impact)
    assert risk.level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
    assert risk.composite_score >= 0.50
    assert len(risk.factors) >= 5
    assert len(risk.reasons) >= 1
