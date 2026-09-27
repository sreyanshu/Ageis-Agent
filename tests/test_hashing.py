from pathlib import Path
from aegis.storage.filesystem import FilesystemStorage
from aegis.storage.hashing import ContentHasher, IncrementalChangeEngine


def test_content_hasher(tmp_path: Path):
    f1 = tmp_path / "test.py"
    f1.write_text("print('hello')", encoding="utf-8")
    h1 = ContentHasher.hash_file(f1)
    assert len(h1) == 64

    # AST hashing
    ast_h1 = ContentHasher.hash_python_ast("def foo():\n    pass\n")
    ast_h2 = ContentHasher.hash_python_ast("def foo():\n    # comment\n    pass\n")
    assert ast_h1 == ast_h2  # Comment differences produce identical AST hash


def test_incremental_change_detection(tmp_path: Path):
    storage = FilesystemStorage(workspace_root=tmp_path)
    engine = IncrementalChangeEngine(workspace_root=tmp_path, storage=storage)

    # Initial state
    f1 = tmp_path / "a.py"
    f1.write_text("a = 1", encoding="utf-8")

    changes1 = engine.detect_changes()
    assert "a.py" in changes1.added_files
    assert changes1.has_changes is True

    # Commit state
    engine.commit_hashes()

    # Second check without modifications
    changes2 = engine.detect_changes()
    assert changes2.has_changes is False
    assert "a.py" in changes2.unchanged_files

    # Modify file
    f1.write_text("a = 2", encoding="utf-8")
    changes3 = engine.detect_changes()
    assert "a.py" in changes3.modified_files

    # Delete file
    f1.unlink()
    changes4 = engine.detect_changes()
    assert "a.py" in changes4.deleted_files
