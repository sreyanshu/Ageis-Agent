"""
Aegis Python AST & Semantic Indexer
Extracts modules, imports, classes, functions, methods, decorators, route definitions,
ORM models, test functions, calls, and relationships from Python source code.
"""

from __future__ import annotations
import ast
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Set

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


class PythonASTIndexer(LanguageIndexer):
    """Deep AST indexer for Python source files."""

    @property
    def language(self) -> str:
        return "python"

    @property
    def supported_extensions(self) -> Set[str]:
        return {".py", ".pyw", ".pyi"}

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
        ast_hash = ContentHasher.hash_python_ast(content)

        # Build module dot-path (e.g. "aegis/core/executor.py" -> "aegis.core.executor")
        module_path = rel_path
        if module_path.endswith(".py"):
            module_path = module_path[:-3]
        dot_module = module_path.replace("/", ".")

        symbols: List[Symbol] = []
        relationships: List[Relationship] = []
        imports: List[str] = []
        exports: List[str] = []

        # File root symbol
        file_symbol_id = f"python:{dot_module}"
        symbols.append(
            Symbol(
                id=file_symbol_id,
                name=Path(rel_path).name,
                qualified_name=dot_module,
                symbol_type=SymbolType.MODULE,
                language=self.language,
                file_path=rel_path,
                line_start=1,
                line_end=len(content.splitlines()) or 1,
                content_hash=file_hash,
            )
        )

        try:
            tree = ast.parse(content, filename=rel_path)
        except SyntaxError:
            # Return partial index with file module only on syntax error
            return IndexedFile(
                file_path=rel_path,
                language=self.language,
                file_hash=file_hash,
                ast_hash=ast_hash,
                symbol_hash=file_hash,
                symbols=symbols,
                relationships=[],
                imports=[],
                exports=[],
            )

        # Visitor to extract semantic entities
        visitor = _PythonASTVisitor(
            dot_module=dot_module,
            rel_path=rel_path,
            content_lines=content.splitlines(),
        )
        visitor.visit(tree)

        symbols.extend(visitor.symbols)
        relationships.extend(visitor.relationships)
        imports.extend(visitor.imports)
        exports.extend(visitor.exports)

        # Link file module to top-level symbols
        for sym in visitor.symbols:
            if "." not in sym.qualified_name:
                relationships.append(
                    Relationship(
                        source_id=file_symbol_id,
                        relation=RelationType.CONTAINS,
                        target_id=sym.id,
                        provenance=Provenance(
                            file_path=rel_path,
                            line_start=sym.line_start,
                            line_end=sym.line_end,
                            confidence=ConfidenceLevel.DIRECT,
                            rationale="File contains top-level symbol",
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


class _PythonASTVisitor(ast.NodeVisitor):
    """Walks the Python AST to extract classes, functions, routes, models, and relations."""

    def __init__(self, dot_module: str, rel_path: str, content_lines: List[str]) -> None:
        self.dot_module = dot_module
        self.rel_path = rel_path
        self.content_lines = content_lines
        self.symbols: List[Symbol] = []
        self.relationships: List[Relationship] = []
        self.imports: List[str] = []
        self.exports: List[str] = []
        self._current_class: Optional[str] = None
        self._current_class_id: Optional[str] = None

    def _get_snippet(self, start_line: int, end_line: int) -> str:
        s = max(0, start_line - 1)
        e = min(len(self.content_lines), end_line)
        return "\n".join(self.content_lines[s:e])

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            target_mod = alias.name
            self.imports.append(target_mod)
            self.relationships.append(
                Relationship(
                    source_id=f"python:{self.dot_module}",
                    relation=RelationType.IMPORTS,
                    target_id=f"python:{target_mod}",
                    provenance=Provenance(
                        file_path=self.rel_path,
                        line_start=node.lineno,
                        line_end=node.end_lineno or node.lineno,
                        snippet=self._get_snippet(node.lineno, node.end_lineno or node.lineno),
                        confidence=ConfidenceLevel.DIRECT,
                        rationale=f"Import statement: import {alias.name}",
                    ),
                )
            )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        target_mod = node.module or ""
        self.imports.append(target_mod)
        for alias in node.names:
            imported_symbol_id = f"python:{target_mod}.{alias.name}" if target_mod else f"python:{alias.name}"
            self.relationships.append(
                Relationship(
                    source_id=f"python:{self.dot_module}",
                    relation=RelationType.IMPORTS,
                    target_id=imported_symbol_id,
                    provenance=Provenance(
                        file_path=self.rel_path,
                        line_start=node.lineno,
                        line_end=node.end_lineno or node.lineno,
                        snippet=self._get_snippet(node.lineno, node.end_lineno or node.lineno),
                        confidence=ConfidenceLevel.DIRECT,
                        rationale=f"Import statement: from {target_mod} import {alias.name}",
                    ),
                )
            )
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        qual_name = f"{self._current_class}.{node.name}" if self._current_class else node.name
        class_id = f"python:{self.dot_module}.{qual_name}"
        end_line = getattr(node, "end_lineno", node.lineno)

        # Detect ORM / Database models
        is_db_model = False
        base_names: List[str] = []
        for base in node.bases:
            b_name = self._resolve_ast_name(base)
            if b_name:
                base_names.append(b_name)
                if any(k in b_name for k in ("Base", "Model", "SQLModel", "Document", "Table")):
                    is_db_model = True

        sym_type = SymbolType.DB_MODEL if is_db_model else SymbolType.CLASS
        node_dump = ast.dump(node, annotate_fields=False)
        content_hash = hashlib.sha256(node_dump.encode("utf-8")).hexdigest()

        docstring = ast.get_docstring(node)
        class_sym = Symbol(
            id=class_id,
            name=node.name,
            qualified_name=qual_name,
            symbol_type=sym_type,
            language="python",
            file_path=self.rel_path,
            line_start=node.lineno,
            line_end=end_line,
            signature=f"class {node.name}({', '.join(base_names)}):",
            docstring=docstring,
            content_hash=content_hash,
            metadata={"bases": base_names, "is_db_model": is_db_model},
        )
        self.symbols.append(class_sym)
        self.exports.append(qual_name)

        # Add inheritance relationships
        for b_name in base_names:
            self.relationships.append(
                Relationship(
                    source_id=class_id,
                    relation=RelationType.INHERITS,
                    target_id=f"python:{b_name}",
                    provenance=Provenance(
                        file_path=self.rel_path,
                        line_start=node.lineno,
                        line_end=node.lineno,
                        snippet=self._get_snippet(node.lineno, node.lineno),
                        confidence=ConfidenceLevel.DIRECT,
                        rationale=f"Class {node.name} inherits from {b_name}",
                    ),
                )
            )

        if is_db_model:
            # Add DB access relationship
            self.relationships.append(
                Relationship(
                    source_id=class_id,
                    relation=RelationType.ACCESSES_DATABASE,
                    target_id=f"db_table:{node.name.lower()}",
                    provenance=Provenance(
                        file_path=self.rel_path,
                        line_start=node.lineno,
                        line_end=end_line,
                        confidence=ConfidenceLevel.HIGH_CONFIDENCE,
                        rationale=f"Class {node.name} defines database model",
                    ),
                )
            )

        # Traverse nested methods with class scope
        prev_class = self._current_class
        prev_class_id = self._current_class_id
        self._current_class = qual_name
        self._current_class_id = class_id

        for item in node.body:
            self.visit(item)

        self._current_class = prev_class
        self._current_class_id = prev_class_id

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._handle_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._handle_function(node, is_async=True)

    def _handle_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_async: bool) -> None:
        qual_name = f"{self._current_class}.{node.name}" if self._current_class else node.name
        func_id = f"python:{self.dot_module}.{qual_name}"
        end_line = getattr(node, "end_lineno", node.lineno)

        # Extract argument signature
        args_list: List[str] = [a.arg for a in node.args.args]
        prefix = "async def " if is_async else "def "
        signature = f"{prefix}{node.name}({', '.join(args_list)})"

        # Determine if test function
        is_test = node.name.startswith("test_") or "pytest" in self.rel_path or "tests/" in self.rel_path
        sym_type = SymbolType.TEST if is_test else (SymbolType.METHOD if self._current_class else SymbolType.FUNCTION)

        node_dump = ast.dump(node, annotate_fields=False)
        content_hash = hashlib.sha256(node_dump.encode("utf-8")).hexdigest()
        docstring = ast.get_docstring(node)

        func_sym = Symbol(
            id=func_id,
            name=node.name,
            qualified_name=qual_name,
            symbol_type=sym_type,
            language="python",
            file_path=self.rel_path,
            line_start=node.lineno,
            line_end=end_line,
            signature=signature,
            docstring=docstring,
            content_hash=content_hash,
            metadata={"is_async": is_async, "args": args_list},
        )
        self.symbols.append(func_sym)
        if not self._current_class:
            self.exports.append(qual_name)

        # If inside a class, establish CONTAINS relationship
        if self._current_class_id:
            self.relationships.append(
                Relationship(
                    source_id=self._current_class_id,
                    relation=RelationType.CONTAINS,
                    target_id=func_id,
                    provenance=Provenance(
                        file_path=self.rel_path,
                        line_start=node.lineno,
                        line_end=end_line,
                        confidence=ConfidenceLevel.DIRECT,
                        rationale="Class contains method",
                    ),
                )
            )

        # Check for API Route decorators (e.g. @app.get("/path"), @router.post("/items"))
        for decorator in node.decorator_list:
            route_info = self._extract_route_decorator(decorator)
            if route_info:
                method, path = route_info
                route_id = f"api:{method}:{path}"
                route_sym = Symbol(
                    id=route_id,
                    name=f"{method} {path}",
                    qualified_name=f"{method} {path}",
                    symbol_type=SymbolType.ROUTE,
                    language="http",
                    file_path=self.rel_path,
                    line_start=node.lineno,
                    line_end=end_line,
                    metadata={"method": method, "path": path, "handler": func_id},
                )
                self.symbols.append(route_sym)
                self.relationships.append(
                    Relationship(
                        source_id=func_id,
                        relation=RelationType.EXPOSES_API,
                        target_id=route_id,
                        provenance=Provenance(
                            file_path=self.rel_path,
                            line_start=node.lineno,
                            line_end=node.lineno,
                            snippet=self._get_snippet(node.lineno, node.lineno),
                            confidence=ConfidenceLevel.HIGH_CONFIDENCE,
                            rationale=f"Handler exposed via {method} {path}",
                        ),
                    )
                )

        # Extract internal function calls
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                called_name = self._resolve_ast_name(child.func)
                if called_name and called_name != node.name:
                    self.relationships.append(
                        Relationship(
                            source_id=func_id,
                            relation=RelationType.CALLS,
                            target_id=f"python:{called_name}",
                            provenance=Provenance(
                                file_path=self.rel_path,
                                line_start=getattr(child, "lineno", node.lineno),
                                line_end=getattr(child, "end_lineno", node.lineno),
                                snippet=self._get_snippet(getattr(child, "lineno", node.lineno), getattr(child, "lineno", node.lineno)),
                                confidence=ConfidenceLevel.INFERRED,
                                rationale=f"Call to {called_name}",
                            ),
                        )
                    )

        # If this is a test function, link it via TESTS relationship to likely targets
        if is_test:
            # E.g. test_get_user -> get_user
            inferred_target = node.name.replace("test_", "")
            if inferred_target:
                self.relationships.append(
                    Relationship(
                        source_id=func_id,
                        relation=RelationType.TESTS,
                        target_id=f"python:{inferred_target}",
                        provenance=Provenance(
                            file_path=self.rel_path,
                            line_start=node.lineno,
                            line_end=end_line,
                            confidence=ConfidenceLevel.HIGH_CONFIDENCE,
                            rationale=f"Test function {node.name} tests target symbol {inferred_target}",
                        ),
                    )
                )

        # Continue traversing inside function body
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                self.visit(item)

    def _resolve_ast_name(self, node: ast.AST) -> Optional[str]:
        """Resolves Name, Attribute, and Call function identifiers."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            val = self._resolve_ast_name(node.value)
            return f"{val}.{node.attr}" if val else node.attr
        return None

    def _extract_route_decorator(self, node: ast.AST) -> Optional[tuple[str, str]]:
        """Detects route decorators e.g. @app.get('/users') or @router.post('/login')."""
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            method = node.func.attr.upper()
            if method in ("GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"):
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    path = node.args[0].value
                    return method, path
        return None
