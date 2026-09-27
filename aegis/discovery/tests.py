"""
Aegis Test Discovery Engine
Discovers existing native test frameworks, test files, test directories, and test count estimates.
"""

from __future__ import annotations
import os
import re
from pathlib import Path
from typing import List, Set
from pydantic import BaseModel, Field


class TestSuiteInfo(BaseModel):
    framework: str
    runner_cmd: str
    test_files: List[str] = Field(default_factory=list)
    test_count_estimate: int = 0
    test_dirs: List[str] = Field(default_factory=list)


class TestDetector:
    """Discovers existing test suites across polyglot ecosystems."""

    IGNORED_DIRS: Set[str] = {
        ".git", ".aegis", "node_modules", ".venv", "venv", "__pycache__",
        ".pytest_cache", "target", "build", "dist", ".idea", ".vscode"
    }

    def detect(self, workspace_root: Path | str) -> List[TestSuiteInfo]:
        root = Path(workspace_root).resolve()
        suites: List[TestSuiteInfo] = []

        python_test_files: List[str] = []
        js_test_files: List[str] = []
        go_test_files: List[str] = []
        rust_test_files: List[str] = []
        java_test_files: List[str] = []

        py_test_cases = 0
        js_test_cases = 0
        go_test_cases = 0

        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in self.IGNORED_DIRS and not d.startswith(".")]

            for f in filenames:
                full_path = Path(dirpath) / f
                rel_path = str(full_path.relative_to(root))

                # Python tests (test_*.py or *_test.py)
                if f.endswith(".py") and (f.startswith("test_") or f.endswith("_test.py")):
                    python_test_files.append(rel_path)
                    py_test_cases += self._count_python_tests(full_path)

                # JS/TS tests (*.test.ts, *.spec.js, etc.)
                elif re.search(r'\.(test|spec)\.(js|jsx|ts|tsx)$', f):
                    js_test_files.append(rel_path)
                    js_test_cases += self._count_js_tests(full_path)

                # Go tests (*_test.go)
                elif f.endswith("_test.go"):
                    go_test_files.append(rel_path)
                    go_test_cases += self._count_go_tests(full_path)

                # Rust test files or tests/ dir
                elif f.endswith(".rs") and ("tests/" in rel_path or f.startswith("test_")):
                    rust_test_files.append(rel_path)

                # Java test files (*Test.java, *Tests.java)
                elif f.endswith(".java") and ("Test" in f or "test" in dirpath.lower()):
                    java_test_files.append(rel_path)

        # 1. Python Test Suite
        if python_test_files or (root / "pytest.ini").is_file() or (root / "conftest.py").is_file():
            test_dirs = list({str(Path(p).parent) for p in python_test_files})
            suites.append(
                TestSuiteInfo(
                    framework="pytest",
                    runner_cmd="pytest",
                    test_files=sorted(python_test_files),
                    test_count_estimate=max(py_test_cases, len(python_test_files)),
                    test_dirs=sorted(test_dirs),
                )
            )

        # 2. JS/TS Test Suite
        if js_test_files:
            fw = "vitest" if (root / "vitest.config.ts").is_file() or (root / "vitest.config.js").is_file() else "jest"
            test_dirs = list({str(Path(p).parent) for p in js_test_files})
            suites.append(
                TestSuiteInfo(
                    framework=fw,
                    runner_cmd="npx vitest run" if fw == "vitest" else "npm test",
                    test_files=sorted(js_test_files),
                    test_count_estimate=max(js_test_cases, len(js_test_files)),
                    test_dirs=sorted(test_dirs),
                )
            )

        # 3. Go Test Suite
        if go_test_files or (root / "go.mod").is_file():
            test_dirs = list({str(Path(p).parent) for p in go_test_files})
            if go_test_files:
                suites.append(
                    TestSuiteInfo(
                        framework="go test",
                        runner_cmd="go test -v ./...",
                        test_files=sorted(go_test_files),
                        test_count_estimate=max(go_test_cases, len(go_test_files)),
                        test_dirs=sorted(test_dirs),
                    )
                )

        # 4. Rust Test Suite
        if rust_test_files or (root / "Cargo.toml").is_file():
            if rust_test_files:
                test_dirs = list({str(Path(p).parent) for p in rust_test_files})
                suites.append(
                    TestSuiteInfo(
                        framework="cargo test",
                        runner_cmd="cargo test",
                        test_files=sorted(rust_test_files),
                        test_count_estimate=len(rust_test_files),
                        test_dirs=sorted(test_dirs),
                    )
                )

        # 5. Java Test Suite
        if java_test_files:
            test_dirs = list({str(Path(p).parent) for p in java_test_files})
            suites.append(
                TestSuiteInfo(
                    framework="junit",
                    runner_cmd="mvn test" if (root / "pom.xml").is_file() else "./gradlew test",
                    test_files=sorted(java_test_files),
                    test_count_estimate=len(java_test_files),
                    test_dirs=sorted(test_dirs),
                )
            )

        return suites

    def _count_python_tests(self, p: Path) -> int:
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
            return len(re.findall(r'def\s+test_[A-Za-z0-9_]+\s*\(', content))
        except Exception:
            return 1

    def _count_js_tests(self, p: Path) -> int:
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
            return len(re.findall(r'(?:it|test)\s*\(\s*["\']', content))
        except Exception:
            return 1

    def _count_go_tests(self, p: Path) -> int:
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
            return len(re.findall(r'func\s+Test[A-Za-z0-9_]+\s*\(', content))
        except Exception:
            return 1
