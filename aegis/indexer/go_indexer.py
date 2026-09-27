"""
Aegis Go AST & Semantic Indexer
Extracts Go packages, imports, structs, interfaces, methods, functions, HTTP routes, and tests.
"""

from __future__ import annotations
import re
import hashlib
from pathlib import Path
from typing import List, Optional, Set, Dict, Any

from aegis.indexer.base import (
    LanguageIndexer,
    IndexedFile,
    Symbol,
    SymbolType,
    Relationship,
    RelationType,
    Provenance,
    ConfidenceLevel,
)
from aegis.storage.hashing import ContentHasher


class GoIndexer(LanguageIndexer):
    """Semantic and syntax-aware indexer for Go source files."""

    @property
    def language(self) -> str:
        return "go"

    @property
    def supported_extensions(self) -> Set[str]:
        return {".go"}

    def index_file(self, workspace_root: Path | str, relative_path: Path | str, content: Optional[str] = None) -> IndexedFile:
        root = Path(workspace_root).resolve()
        rel_path = str(relative_path).replace("\\", "/")
        full_path = root / rel_path

        if content is None:
            if not full_path.is_file():
                return IndexedFile(
                    file_path=rel_path,
                    language=self.language,
                    file_hash="",
                    ast_hash="",
                    symbol_hash="",
                )
            content = full_path.read_text(encoding="utf-8", errors="ignore")

        file_hash = ContentHasher.hash_bytes(content.encode("utf-8"))
        clean_content = re.sub(r'//.*|/\*[\s\S]*?\*/', '', content).strip()
        ast_hash = ContentHasher.hash_bytes(clean_content.encode("utf-8"))

        symbols: List[Symbol] = []
        relationships: List[Relationship] = []
        imports: List[str] = []
        exports: List[str] = []

        lines = content.splitlines()

        # 1. Package declaration
        pkg_name = "main"
        for line in lines:
            m_pkg = re.match(r'^\s*package\s+([A-Za-z0-9_]+)', line)
            if m_pkg:
                pkg_name = m_pkg.group(1)
                break

        pkg_id = f"go:{pkg_name}"
        file_symbol_id = f"go:{pkg_name}:{rel_path}"
        symbols.append(
            Symbol(
                id=file_symbol_id,
                name=Path(rel_path).name,
                qualified_name=f"{pkg_name}.{Path(rel_path).stem}",
                symbol_type=SymbolType.FILE,
                language=self.language,
                file_path=rel_path,
                line_start=1,
                line_end=len(lines) or 1,
                content_hash=file_hash,
                metadata={"package": pkg_name},
            )
        )

        # 2. Imports
        import_block = False
        import_single_pattern = re.compile(r'import\s+["\']([^"\']+)["\']')
        import_multi_line = re.compile(r'^\s*(?:([A-Za-z0-9_]+)\s+)?["\']([^"\']+)["\']')

        for idx, line in enumerate(lines, start=1):
            if re.match(r'^\s*import\s*\(', line):
                import_block = True
                continue
            if import_block:
                if re.match(r'^\s*\)', line):
                    import_block = False
                    continue
                m = import_multi_line.search(line)
                if m:
                    imp_pkg = m.group(2)
                    imports.append(imp_pkg)
                    relationships.append(
                        Relationship(
                            source_id=file_symbol_id,
                            relation=RelationType.IMPORTS,
                            target_id=f"go:{imp_pkg}",
                            provenance=Provenance(
                                file_path=rel_path,
                                line_start=idx,
                                line_end=idx,
                                snippet=line.strip(),
                                confidence=ConfidenceLevel.DIRECT,
                            ),
                        )
                    )
            else:
                m = import_single_pattern.search(line)
                if m:
                    imp_pkg = m.group(1)
                    imports.append(imp_pkg)
                    relationships.append(
                        Relationship(
                            source_id=file_symbol_id,
                            relation=RelationType.IMPORTS,
                            target_id=f"go:{imp_pkg}",
                            provenance=Provenance(
                                file_path=rel_path,
                                line_start=idx,
                                line_end=idx,
                                snippet=line.strip(),
                                confidence=ConfidenceLevel.DIRECT,
                            ),
                        )
                    )

        # 3. Structs & Interfaces (type X struct, type Y interface)
        type_pattern = re.compile(r'type\s+([A-Za-z0-9_]+)\s+(struct|interface)')
        for idx, line in enumerate(lines, start=1):
            m = type_pattern.search(line)
            if m:
                t_name = m.group(1)
                t_kind = m.group(2)
                t_id = f"go:{pkg_name}.{t_name}"
                sym_type = SymbolType.INTERFACE if t_kind == "interface" else SymbolType.CLASS
                symbols.append(
                    Symbol(
                        id=t_id,
                        name=t_name,
                        qualified_name=f"{pkg_name}.{t_name}",
                        symbol_type=sym_type,
                        language=self.language,
                        file_path=rel_path,
                        line_start=idx,
                        line_end=idx,
                        signature=line.strip(),
                        content_hash=hashlib.sha256(line.encode("utf-8")).hexdigest(),
                    )
                )
                if t_name[0].isupper():
                    exports.append(t_name)

        # 4. Functions & Methods (func (r *Receiver) Method(...) or func Function(...))
        method_pattern = re.compile(r'func\s*\(\s*(?:[A-Za-z0-9_]+\s+)?\*?([A-Za-z0-9_]+)\s*\)\s*([A-Za-z0-9_]+)\s*\(([^)]*)\)')
        func_pattern = re.compile(r'func\s+([A-Za-z0-9_]+)\s*\(([^)]*)\)')

        for idx, line in enumerate(lines, start=1):
            m_meth = method_pattern.search(line)
            if m_meth:
                receiver = m_meth.group(1)
                m_name = m_meth.group(2)
                m_args = m_meth.group(3)
                m_id = f"go:{pkg_name}.{receiver}.{m_name}"
                is_test = m_name.startswith("Test") or rel_path.endswith("_test.go")

                symbols.append(
                    Symbol(
                        id=m_id,
                        name=m_name,
                        qualified_name=f"{receiver}.{m_name}",
                        symbol_type=SymbolType.TEST if is_test else SymbolType.METHOD,
                        language=self.language,
                        file_path=rel_path,
                        line_start=idx,
                        line_end=idx,
                        signature=f"func ({receiver}) {m_name}({m_args})",
                        content_hash=hashlib.sha256(line.encode("utf-8")).hexdigest(),
                        metadata={"receiver": receiver},
                    )
                )
                # Link method to receiver struct
                relationships.append(
                    Relationship(
                        source_id=f"go:{pkg_name}.{receiver}",
                        relation=RelationType.CONTAINS,
                        target_id=m_id,
                        provenance=Provenance(
                            file_path=rel_path,
                            line_start=idx,
                            line_end=idx,
                            confidence=ConfidenceLevel.DIRECT,
                        ),
                    )
                )
                if m_name[0].isupper():
                    exports.append(f"{receiver}.{m_name}")
                continue

            m_fn = func_pattern.search(line)
            if m_fn:
                fn_name = m_fn.group(1)
                fn_args = m_fn.group(2)
                fn_id = f"go:{pkg_name}.{fn_name}"
                is_test = fn_name.startswith("Test") or rel_path.endswith("_test.go")

                symbols.append(
                    Symbol(
                        id=fn_id,
                        name=fn_name,
                        qualified_name=f"{pkg_name}.{fn_name}",
                        symbol_type=SymbolType.TEST if is_test else SymbolType.FUNCTION,
                        language=self.language,
                        file_path=rel_path,
                        line_start=idx,
                        line_end=idx,
                        signature=f"func {fn_name}({fn_args})",
                        content_hash=hashlib.sha256(line.encode("utf-8")).hexdigest(),
                    )
                )
                if fn_name[0].isupper():
                    exports.append(fn_name)

        # 5. Route definitions (Gin / Chi / standard: r.GET("/ping", ...))
        route_pattern = re.compile(r'(?:r|router|api|engine|mux)\.(GET|POST|PUT|DELETE|PATCH|HandleFunc|Handle)\s*\(\s*["\']([^"\']+)["\']')
        for idx, line in enumerate(lines, start=1):
            m_r = route_pattern.search(line)
            if m_r:
                method = m_r.group(1).upper()
                if method in ("HANDLEFUNC", "HANDLE"):
                    method = "ANY"
                path = m_r.group(2)
                route_id = f"api:{method}:{path}"
                symbols.append(
                    Symbol(
                        id=route_id,
                        name=f"{method} {path}",
                        qualified_name=f"{method} {path}",
                        symbol_type=SymbolType.ROUTE,
                        language="http",
                        file_path=rel_path,
                        line_start=idx,
                        line_end=idx,
                        metadata={"method": method, "path": path},
                    )
                )
                relationships.append(
                    Relationship(
                        source_id=file_symbol_id,
                        relation=RelationType.EXPOSES_API,
                        target_id=route_id,
                        provenance=Provenance(
                            file_path=rel_path,
                            line_start=idx,
                            line_end=idx,
                            snippet=line.strip(),
                            confidence=ConfidenceLevel.HIGH_CONFIDENCE,
                            rationale=f"Go HTTP route {method} {path}",
                        ),
                    )
                )

        # Compute aggregate symbol hash
        symbol_hasher = hashlib.sha256()
        for sym in sorted(symbols, key=lambda s: s.id):
            symbol_hasher.update(sym.id.encode("utf-8"))
            symbol_hasher.update(sym.content_hash.encode("utf-8"))
            if sym.signature:
                symbol_hasher.update(sym.signature.encode("utf-8"))

        return IndexedFile(
            file_path=rel_path,
            language=self.language,
            file_hash=file_hash,
            ast_hash=ast_hash,
            symbol_hash=symbol_hasher.hexdigest(),
            symbols=symbols,
            relationships=relationships,
            imports=sorted(list(set(imports))),
            exports=sorted(list(set(exports))),
        )
