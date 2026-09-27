from pathlib import Path
from aegis.core.orchestrator import AegisEngine
from aegis.impact.models import SymbolChangeType


def test_change_impact_on_fastapi_fixture(tmp_path: Path):
    # Copy fixture to temp dir
    fixture_dir = Path(__file__).parent / "fixtures" / "projects" / "python_fastapi"
    import shutil
    shutil.copytree(fixture_dir, tmp_path / "app_copy")

    engine = AegisEngine(workspace_root=tmp_path / "app_copy")
    engine.init_workspace()

    # Initial impact check (clean state)
    impact_initial = engine.analyze_impact()
    assert impact_initial.has_changes is False
    assert len(impact_initial.changed_symbols) == 0

    # Modify repository file
    repo_file = tmp_path / "app_copy" / "app" / "repositories.py"
    repo_file.write_text(
        "from app.models import User, Item\n\nclass UserRepository:\n    def get_by_id(self, user_id: int, include_deleted: bool = False) -> User:\n        return User()\n",
        encoding="utf-8",
    )

    impact = engine.analyze_impact()
    assert impact.has_changes is True
    assert impact.changed_files_count == 1

    changed_names = [s.name for s in impact.changed_symbols]
    assert "get_by_id" in changed_names

    sig_changes = [s for s in impact.changed_symbols if s.change_type == SymbolChangeType.SIGNATURE_CHANGED]
    assert len(sig_changes) >= 1
    assert "include_deleted" in (sig_changes[0].signature or "")

    assert impact.blast_radius.total_affected >= 0
