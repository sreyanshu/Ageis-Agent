# Aegis AST Indexing Architecture

## 1. Overview
Aegis indexes source code into abstract semantic representations using language-specific AST and pattern indexers conforming to the `LanguageIndexer` protocol.

## 2. Polyglot Language Support
* **Python (`PythonASTIndexer`):** Uses Python's native `ast` module to extract classes, methods, functions, async handlers, route decorators (`@app.get(...)`), database models (inheriting from `Base`/`Model`), imports, and `test_*` functions.
* **JavaScript / TypeScript (`JavaScriptTypeScriptIndexer`):** Extracts ES6 and CommonJS imports/exports, TypeScript interfaces and types, classes, functions, arrow handlers, React components, and Express/Fetch route contracts.
* **Go (`GoIndexer`):** Extracts packages, imports, structs, interfaces, methods with receiver structs, Gin/HTTP routes, and `Test*` functions.

## 3. Incremental Indexing Engine
The `SymbolIndex` avoids redundant work by maintaining:
1. `file_hash`: SHA-256 of raw file bytes.
2. `ast_hash`: SHA-256 of normalized AST representation (comment/whitespace invariant).
3. `symbol_hash`: SHA-256 of symbols and signatures.

Files whose raw bytes have not changed are skipped instantly during graph builds. Files where only comments changed do not trigger symbol or relationship recomputation.
