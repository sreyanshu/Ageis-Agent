"""
Aegis Build System Discovery Engine
Detects package managers, build automation tools, lockfiles, and project manifests.
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field


class BuildSystemInfo(BaseModel):
    name: str
    manifest_file: str
    lock_file: Optional[str] = None
    default_build_cmd: Optional[str] = None
    default_test_cmd: Optional[str] = None


class BuildSystemDetector:
    """Detects build tools and manifests across polyglot ecosystems."""

    def detect(self, workspace_root: Path | str) -> List[BuildSystemInfo]:
        root = Path(workspace_root).resolve()
        detected: List[BuildSystemInfo] = []

        # 1. Node.js Ecosystem
        if (root / "package.json").is_file():
            lock = None
            name = "npm"
            cmd_prefix = "npm"

            if (root / "pnpm-lock.yaml").is_file():
                name = "pnpm"
                lock = "pnpm-lock.yaml"
                cmd_prefix = "pnpm"
            elif (root / "yarn.lock").is_file():
                name = "yarn"
                lock = "yarn.lock"
                cmd_prefix = "yarn"
            elif (root / "bun.lockb").is_file() or (root / "bun.lock").is_file():
                name = "bun"
                lock = "bun.lockb" if (root / "bun.lockb").is_file() else "bun.lock"
                cmd_prefix = "bun"
            elif (root / "package-lock.json").is_file():
                lock = "package-lock.json"

            detected.append(
                BuildSystemInfo(
                    name=name,
                    manifest_file="package.json",
                    lock_file=lock,
                    default_build_cmd=f"{cmd_prefix} run build",
                    default_test_cmd=f"{cmd_prefix} test",
                )
            )

        # 2. Python Ecosystem
        if (root / "pyproject.toml").is_file():
            lock = None
            name = "pip/pyproject"
            content = (root / "pyproject.toml").read_text(encoding="utf-8", errors="ignore").lower()

            if (root / "poetry.lock").is_file() or "[tool.poetry]" in content:
                name = "poetry"
                lock = "poetry.lock" if (root / "poetry.lock").is_file() else None
            elif (root / "pdm.lock").is_file() or "[tool.pdm]" in content:
                name = "pdm"
                lock = "pdm.lock" if (root / "pdm.lock").is_file() else None
            elif (root / "uv.lock").is_file() or "[tool.uv]" in content:
                name = "uv"
                lock = "uv.lock" if (root / "uv.lock").is_file() else None

            detected.append(
                BuildSystemInfo(
                    name=name,
                    manifest_file="pyproject.toml",
                    lock_file=lock,
                    default_build_cmd="python -m build" if name != "poetry" else "poetry build",
                    default_test_cmd="pytest" if name != "poetry" else "poetry run pytest",
                )
            )
        elif (root / "requirements.txt").is_file():
            detected.append(
                BuildSystemInfo(
                    name="pip",
                    manifest_file="requirements.txt",
                    default_build_cmd="pip install -r requirements.txt",
                    default_test_cmd="pytest",
                )
            )
        elif (root / "Pipfile").is_file():
            detected.append(
                BuildSystemInfo(
                    name="pipenv",
                    manifest_file="Pipfile",
                    lock_file="Pipfile.lock" if (root / "Pipfile.lock").is_file() else None,
                    default_build_cmd="pipenv install",
                    default_test_cmd="pipenv run pytest",
                )
            )

        # 3. Rust Ecosystem
        if (root / "Cargo.toml").is_file():
            detected.append(
                BuildSystemInfo(
                    name="cargo",
                    manifest_file="Cargo.toml",
                    lock_file="Cargo.lock" if (root / "Cargo.lock").is_file() else None,
                    default_build_cmd="cargo build",
                    default_test_cmd="cargo test",
                )
            )

        # 4. Go Ecosystem
        if (root / "go.mod").is_file():
            detected.append(
                BuildSystemInfo(
                    name="go modules",
                    manifest_file="go.mod",
                    lock_file="go.sum" if (root / "go.sum").is_file() else None,
                    default_build_cmd="go build ./...",
                    default_test_cmd="go test -v ./...",
                )
            )

        # 5. Java / Kotlin Ecosystem
        if (root / "pom.xml").is_file():
            detected.append(
                BuildSystemInfo(
                    name="maven",
                    manifest_file="pom.xml",
                    default_build_cmd="mvn clean compile",
                    default_test_cmd="mvn test",
                )
            )
        if (root / "build.gradle").is_file() or (root / "build.gradle.kts").is_file():
            gradle_f = "build.gradle.kts" if (root / "build.gradle.kts").is_file() else "build.gradle"
            wrapper = "./gradlew" if (root / "gradlew").is_file() else "gradle"
            detected.append(
                BuildSystemInfo(
                    name="gradle",
                    manifest_file=gradle_f,
                    default_build_cmd=f"{wrapper} build",
                    default_test_cmd=f"{wrapper} test",
                )
            )

        # 6. PHP / Composer
        if (root / "composer.json").is_file():
            detected.append(
                BuildSystemInfo(
                    name="composer",
                    manifest_file="composer.json",
                    lock_file="composer.lock" if (root / "composer.lock").is_file() else None,
                    default_build_cmd="composer install",
                    default_test_cmd="./vendor/bin/phpunit",
                )
            )

        # 7. Make / CMake
        if (root / "Makefile").is_file():
            detected.append(
                BuildSystemInfo(
                    name="make",
                    manifest_file="Makefile",
                    default_build_cmd="make",
                    default_test_cmd="make test",
                )
            )
        if (root / "CMakeLists.txt").is_file():
            detected.append(
                BuildSystemInfo(
                    name="cmake",
                    manifest_file="CMakeLists.txt",
                    default_build_cmd="cmake --build build",
                    default_test_cmd="ctest",
                )
            )

        return detected
