"""
Aegis JavaScript & TypeScript Semantic Indexer
Extracts modules, ES/CommonJS imports, exports, classes, functions, React UI components,
interfaces, API routes, and test suites from JS/TS codebases.
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


class JavaScriptTypeScriptIndexer(LanguageIndexer):
    """Semantic and syntax-aware indexer for JavaScript and TypeScript files."""

    @property
    def language(self) -> str:
        return "typescript"

    @property
    def supported_extensions(self) -> Set[str]:
        return {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}

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
        ast_hash = ContentHasher.hash_bytes(re.sub(r'//.*|/\*[\s\S]*?\*/', '', content).strip().encode("utf-8"))

        module_name = Path(rel_path).stem
        dot_module = rel_path.replace("/", ".").replace(Path(rel_path).suffix, "")

        symbols: List[Symbol] = []
        relationships: List[Relationship] = []
        imports: List[str] = []
        exports: List[str] = []

        file_symbol_id = f"ts:{dot_module}"
        symbols.append(
            Symbol(
                id=file_symbol_id,
                name=Path(rel_path).name,
                qualified_name=dot_module,
                symbol_type=SymbolType.MODULE,
                language="typescript" if rel_path.endswith((".ts", ".tsx")) else "javascript",
                file_path=rel_path,
                line_start=1,
                line_end=len(content.splitlines()) or 1,
                content_hash=file_hash,
            )
        )

        lines = content.splitlines()

        # 1. Imports
        # import ... from 'pkg' or const x = require('pkg')
        import_es_pattern = re.compile(r'import\s+(?:(?:\{([^}]+)\}|\*\s+as\s+([A-Za-z0-9_]+)|([A-Za-z0-9_]+))\s+from\s+)?["\']([^"\']+)["\']')
        require_pattern = re.compile(r'(?:const|let|var)\s+(?:\{([^}]+)\}|([A-Za-z0-9_]+))\s*=\s*require\(["\']([^"\']+)["\']\)')

        for idx, line in enumerate(lines, start=1):
            m_es = import_es_pattern.search(line)
            if m_es:
                named, star, default, module_spec = m_es.groups()
                imports.append(module_spec)
                relationships.append(
                    Relationship(
                        source_id=file_symbol_id,
                        relation=RelationType.IMPORTS,
                        target_id=f"ts:{module_spec}",
                        provenance=Provenance(
                            file_path=rel_path,
                            line_start=idx,
                            line_end=idx,
                            snippet=line.strip(),
                            confidence=ConfidenceLevel.DIRECT,
                            rationale=f"ES import from {module_spec}",
                        ),
                    )
                )

            m_req = require_pattern.search(line)
            if m_req:
                named, default, module_spec = m_req.groups()
                imports.append(module_spec)
                relationships.append(
                    Relationship(
                        source_id=file_symbol_id,
                        relation=RelationType.IMPORTS,
                        target_id=f"ts:{module_spec}",
                        provenance=Provenance(
                            file_path=rel_path,
                            line_start=idx,
                            line_end=idx,
                            snippet=line.strip(),
                            confidence=ConfidenceLevel.DIRECT,
                            rationale=f"CommonJS require from {module_spec}",
                        ),
                    )
                )

        # 2. Interfaces and Type aliases (TypeScript)
        if rel_path.endswith((".ts", ".tsx")):
            interface_pattern = re.compile(r'(?:export\s+)?interface\s+([A-Za-z0-9_]+)(?:\s+extends\s+([A-Za-z0-9_]+))?')
            for idx, line in enumerate(lines, start=1):
                m = interface_pattern.search(line)
                if m:
                    iface_name = m.group(1)
                    extends_name = m.group(2)
                    iface_id = f"ts:{dot_module}.{iface_name}"
                    symbols.append(
                        Symbol(
                            id=iface_id,
                            name=iface_name,
                            qualified_name=iface_name,
                            symbol_type=SymbolType.INTERFACE,
                            language="typescript",
                            file_path=rel_path,
                            line_start=idx,
                            line_end=idx,
                            signature=line.strip(),
                            content_hash=hashlib.sha256(line.encode("utf-8")).hexdigest(),
                        )
                    )
                    exports.append(iface_name)
                    if extends_name:
                        relationships.append(
                            Relationship(
                                source_id=iface_id,
                                relation=RelationType.INHERITS,
                                target_id=f"ts:{extends_name}",
                                provenance=Provenance(
                                    file_path=rel_path,
                                    line_start=idx,
                                    line_end=idx,
                                    confidence=ConfidenceLevel.DIRECT,
                                    rationale=f"Interface {iface_name} extends {extends_name}",
                                ),
                            )
                        )

        # 3. Classes
        class_pattern = re.compile(r'(?:export\s+(?:default\s+)?)?class\s+([A-Za-z0-9_]+)(?:\s+extends\s+([A-Za-z0-9_]+))?(?:\s+implements\s+([A-Za-z0-9_,\s]+))?')
        for idx, line in enumerate(lines, start=1):
            m = class_pattern.search(line)
            if m:
                cls_name = m.group(1)
                extends_name = m.group(2)
                implements_names = m.group(3)
                cls_id = f"ts:{dot_module}.{cls_name}"
                is_component = rel_path.endswith((".tsx", ".jsx")) and (cls_name.startswith("Component") or (extends_name and "Component" in extends_name))
                sym_type = SymbolType.COMPONENT if is_component else SymbolType.CLASS
                symbols.append(
                    Symbol(
                        id=cls_id,
                        name=cls_name,
                        qualified_name=cls_name,
                        symbol_type=sym_type,
                        language="typescript" if rel_path.endswith((".ts", ".tsx")) else "javascript",
                        file_path=rel_path,
                        line_start=idx,
                        line_end=idx,
                        signature=line.strip(),
                        content_hash=hashlib.sha256(line.encode("utf-8")).hexdigest(),
                        metadata={"is_component": is_component, "extends": extends_name},
                    )
                )
                exports.append(cls_name)
                if extends_name:
                    relationships.append(
                        Relationship(
                            source_id=cls_id,
                            relation=RelationType.INHERITS,
                            target_id=f"ts:{extends_name}",
                            provenance=Provenance(
                                file_path=rel_path,
                                line_start=idx,
                                line_end=idx,
                                confidence=ConfidenceLevel.DIRECT,
                            ),
                        )
                    )

        # 4. Functions / React Components / Hooks
        func_pattern = re.compile(r'(?:export\s+(?:default\s+)?)?(?:async\s+)?function\s+([A-Za-z0-9_]+)\s*\(([^)]*)\)')
        const_func_pattern = re.compile(r'(?:export\s+)?(?:const|let|var)\s+([A-Za-z0-9_]+)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*(?::\s*[^=]+)?\s*=>')

        for idx, line in enumerate(lines, start=1):
            m_func = func_pattern.search(line) or const_func_pattern.search(line)
            if m_func:
                f_name = m_func.group(1)
                f_args = m_func.group(2)
                f_id = f"ts:{dot_module}.{f_name}"
                # Detect React functional components: PascalCase and inside .tsx / .jsx
                is_component = (rel_path.endswith((".tsx", ".jsx")) or "components/" in rel_path) and f_name[0].isupper()
                is_test = f_name.startswith("test") or "tests/" in rel_path
                sym_type = SymbolType.COMPONENT if is_component else (SymbolType.TEST if is_test else SymbolType.FUNCTION)

                symbols.append(
                    Symbol(
                        id=f_id,
                        name=f_name,
                        qualified_name=f_name,
                        symbol_type=sym_type,
                        language="typescript" if rel_path.endswith((".ts", ".tsx")) else "javascript",
                        file_path=rel_path,
                        line_start=idx,
                        line_end=idx,
                        signature=f"function {f_name}({f_args})",
                        content_hash=hashlib.sha256(line.encode("utf-8")).hexdigest(),
                        metadata={"is_component": is_component, "args": f_args.strip()},
                    )
                )
                exports.append(f_name)

        # 5. Tests (describe / it / test blocks in Jest/Vitest/Mocha)
        test_block_pattern = re.compile(r'(?:it|test)\s*\(\s*["\']([^"\']+)["\']')
        for idx, line in enumerate(lines, start=1):
            m_t = test_block_pattern.search(line)
            if m_t:
                test_name = m_t.group(1)
                safe_test_name = re.sub(r'[^a-zA-Z0-9_]', '_', test_name)
                t_id = f"ts:{dot_module}.test_{safe_test_name}_{idx}"
                symbols.append(
                    Symbol(
                        id=t_id,
                        name=test_name,
                        qualified_name=f"test:{test_name}",
                        symbol_type=SymbolType.TEST,
                        language="javascript",
                        file_path=rel_path,
                        line_start=idx,
                        line_end=idx,
                        signature=line.strip(),
                        content_hash=hashlib.sha256(line.encode("utf-8")).hexdigest(),
                    )
                )

        # 6. Backend API route handlers (Express/Fastify: app.get('/path'), router.post('/path'))
        route_pattern = re.compile(r'(?:app|router)\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']')
        for idx, line in enumerate(lines, start=1):
            m_r = route_pattern.search(line)
            if m_r:
                method = m_r.group(1).upper()
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
                            rationale=f"Express route handler {method} {path}",
                        ),
                    )
                )

        # 7. Frontend API consumption (fetch('/api/users') or axios.get('/api/users'))
        fetch_pattern = re.compile(r'(?:fetch|axios\.(?:get|post|put|delete))\s*\(\s*["\'](/[^"\']+)["\']')
        for idx, line in enumerate(lines, start=1):
            m_f = fetch_pattern.search(line)
            if m_f:
                api_path = m_f.group(1)
                relationships.append(
                    Relationship(
                        source_id=file_symbol_id,
                        relation=RelationType.CONSUMES_API,
                        target_id=f"api:ANY:{api_path}",
                        provenance=Provenance(
                            file_path=rel_path,
                            line_start=idx,
                            line_end=idx,
                            snippet=line.strip(),
                            confidence=ConfidenceLevel.HEURISTIC,
                            rationale=f"Frontend HTTP request to {api_path}",
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
