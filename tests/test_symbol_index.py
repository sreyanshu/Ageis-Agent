from pathlib import Path
from aegis.indexer.symbol_index import SymbolIndex
from aegis.storage.filesystem import FilesystemStorage


def test_symbol_index_lifecycle(tmp_path: Path):
    storage = FilesystemStorage(workspace_root=tmp_path)
    sym_idx = SymbolIndex(workspace_root=tmp_path, storage=storage)

    # 1. Create file 1
    f1 = tmp_path / "service.py"
    f1.write_text("def process_data(x: int) -> int:\n    return x * 2\n", encoding="utf-8")

    reindexed, skipped = sym_idx.index_workspace()
    assert reindexed == 1
    assert skipped == 0
    assert "python:service.process_data" in sym_idx.symbols

    # 2. Second pass without changes
    reindexed2, skipped2 = sym_idx.index_workspace()
    assert reindexed2 == 0
    assert skipped2 == 1

    # 3. Comment change (AST remains unchanged)
    old_ast_hash = sym_idx.files_meta["service.py"].ast_hash
    f1.write_text("# Process data with multiplier\ndef process_data(x: int) -> int:\n    return x * 2\n", encoding="utf-8")

    reindexed3, skipped3 = sym_idx.index_workspace()
    assert reindexed3 == 1
    new_ast_hash = sym_idx.files_meta["service.py"].ast_hash
    assert old_ast_hash == new_ast_hash

    # 4. Modify signature
    f1.write_text("def process_data(x: int, multiplier: int = 2) -> int:\n    return x * multiplier\n", encoding="utf-8")
    reindexed4, _ = sym_idx.index_workspace()
    assert reindexed4 == 1
    sym = sym_idx.symbols["python:service.process_data"]
    assert "multiplier" in (sym.signature or "")

    # 5. Delete file
    f1.unlink()
    sym_idx.index_workspace()
    assert "python:service.process_data" not in sym_idx.symbols
