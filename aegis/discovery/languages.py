"""
Aegis Language Discovery Engine
Detects polyglot programming languages, file distribution, source counts, and runtime version hints.
"""

from __future__ import annotations
import os
import re
from pathlib import Path
from typing import Dict, List, Set, Optional
from pydantic import BaseModel, Field


class LanguageInfo(BaseModel):
    name: str
    extensions: List[str]
    file_count: int = 0
    percentage: float = 0.0
    version_hint: Optional[str] = None
    primary: bool = False


class LanguageDetector:
    """Discovers languages in an arbitrary codebase."""

    LANGUAGE_EXTENSIONS: Dict[str, List[str]] = {
        "Python": [".py", ".pyw", ".pyi"],
        "TypeScript": [".ts", ".tsx", ".mts", ".cts"],
        "JavaScript": [".js", ".jsx", ".mjs", ".cjs"],
        "Go": [".go"],
        "Rust": [".rs"],
        "Java": [".java"],
        "Kotlin": [".kt", ".kts"],
        "C#": [".cs", ".csx"],
        "C": [".c", ".h"],
        "C++": [".cpp", ".cc", ".cxx", ".hpp", ".hxx"],
        "PHP": [".php", ".phtml"],
        "Ruby": [".rb", ".rake"],
        "Swift": [".swift"],
        "Dart": [".dart"],
        "Shell": [".sh", ".bash", ".zsh"],
        "HTML": [".html", ".htm"],
        "CSS": [".css", ".scss", ".sass", ".less"],
        "SQL": [".sql"],
    }

    IGNORED_DIRS: Set[str] = {
        ".git", ".aegis", "node_modules", ".venv", "venv", "__pycache__",
        ".pytest_cache", "target", "build", "dist", ".idea", ".vscode",
        ".turbo", ".next", ".nuxt", "coverage", ".tox", "vendor"
    }

    def detect(self, workspace_root: Path | str) -> List[LanguageInfo]:
        root = Path(workspace_root).resolve()
        counts: Dict[str, int] = {lang: 0 for lang in self.LANGUAGE_EXTENSIONS}
        ext_to_lang: Dict[str, str] = {}
        for lang, exts in self.LANGUAGE_EXTENSIONS.items():
            for ext in exts:
                ext_to_lang[ext] = lang

        total_files = 0
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in self.IGNORED_DIRS and not d.startswith(".")]
            for f in filenames:
                if f.startswith("."):
                    continue
                ext = Path(f).suffix.lower()
                if ext in ext_to_lang:
                    lang = ext_to_lang[ext]
                    counts[lang] += 1
                    total_files += 1

        results: List[LanguageInfo] = []
        if total_files == 0:
            return results

        sorted_langs = sorted(
            [(lang, count) for lang, count in counts.items() if count > 0],
            key=lambda x: x[1],
            reverse=True,
        )

        for idx, (lang, count) in enumerate(sorted_langs):
            percentage = round((count / total_files) * 100.0, 2)
            version_hint = self._detect_version_hint(root, lang)
            results.append(
                LanguageInfo(
                    name=lang,
                    extensions=self.LANGUAGE_EXTENSIONS[lang],
                    file_count=count,
                    percentage=percentage,
                    version_hint=version_hint,
                    primary=(idx == 0),
                )
            )

        return results

    def _detect_version_hint(self, root: Path, language: str) -> Optional[str]:
        """Inspects manifests and config files for runtime version pins."""
        if language == "Python":
            for filename in [".python-version", "pyproject.toml", "Pipfile", "runtime.txt"]:
                p = root / filename
                if p.is_file():
                    content = p.read_text(encoding="utf-8", errors="ignore")
                    if filename == ".python-version":
                        return content.strip()
                    m = re.search(r'python\s*=\s*["\']([^"\']+)["\']', content)
                    if m:
                        return m.group(1)
                    m = re.search(r'requires-python\s*=\s*["\']([^"\']+)["\']', content)
                    if m:
                        return m.group(1)
        elif language in ("JavaScript", "TypeScript"):
            for filename in [".nvmrc", ".node-version", "package.json"]:
                p = root / filename
                if p.is_file():
                    content = p.read_text(encoding="utf-8", errors="ignore")
                    if filename in (".nvmrc", ".node-version"):
                        return content.strip()
                    m = re.search(r'"node":\s*"([^"]+)"', content)
                    if m:
                        return m.group(1)
        elif language == "Go":
            go_mod = root / "go.mod"
            if go_mod.is_file():
                content = go_mod.read_text(encoding="utf-8", errors="ignore")
                m = re.search(r"^go\s+([0-9\.]+)", content, re.MULTILINE)
                if m:
                    return m.group(1)
        elif language == "Rust":
            rust_toolchain = root / "rust-toolchain"
            if rust_toolchain.is_file():
                return rust_toolchain.read_text(encoding="utf-8", errors="ignore").strip()
            cargo_toml = root / "Cargo.toml"
            if cargo_toml.is_file():
                content = cargo_toml.read_text(encoding="utf-8", errors="ignore")
                m = re.search(r'rust-version\s*=\s*["\']([^"\']+)["\']', content)
                if m:
                    return m.group(1)
        elif language in ("Java", "Kotlin"):
            pom = root / "pom.xml"
            if pom.is_file():
                content = pom.read_text(encoding="utf-8", errors="ignore")
                m = re.search(r"<java\.version>([^<]+)</java\.version>", content)
                if m:
                    return m.group(1)
            gradle = root / "build.gradle"
            if gradle.is_file():
                content = gradle.read_text(encoding="utf-8", errors="ignore")
                m = re.search(r"sourceCompatibility\s*=\s*['\"]?([0-9\._]+)['\"]?", content)
                if m:
                    return m.group(1)
        return None
