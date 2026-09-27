"""
Aegis Framework Discovery Engine
Discovers backend, frontend, full-stack, mobile, and desktop frameworks from project manifests and code patterns.
"""

from __future__ import annotations
import json
import re
from pathlib import Path
from typing import List, Optional, Set
from pydantic import BaseModel, Field


class FrameworkInfo(BaseModel):
    name: str
    category: str  # backend, frontend, fullstack, mobile, ml, desktop
    confidence: float = 1.0
    version: Optional[str] = None
    manifest_source: Optional[str] = None


class FrameworkDetector:
    """Detects web, mobile, and system frameworks across multiple language ecosystems."""

    def detect(self, workspace_root: Path | str) -> List[FrameworkInfo]:
        root = Path(workspace_root).resolve()
        detected: List[FrameworkInfo] = []
        seen: Set[str] = set()

        def add_fw(info: FrameworkInfo) -> None:
            if info.name not in seen:
                seen.add(info.name)
                detected.append(info)

        # 1. Node.js / JavaScript / TypeScript Frameworks (package.json)
        pkg_json_files = list(root.glob("package.json")) + list(root.glob("*/package.json"))
        for pkg_path in pkg_json_files:
            try:
                data = json.loads(pkg_path.read_text(encoding="utf-8", errors="ignore"))
                deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}

                if "next" in deps:
                    add_fw(FrameworkInfo(name="Next.js", category="fullstack", version=deps["next"], manifest_source=str(pkg_path.relative_to(root))))
                if "react" in deps and "next" not in deps:
                    add_fw(FrameworkInfo(name="React", category="frontend", version=deps["react"], manifest_source=str(pkg_path.relative_to(root))))
                if "vue" in deps or "nuxt" in deps:
                    name = "Nuxt" if "nuxt" in deps else "Vue"
                    ver = deps.get("nuxt") or deps.get("vue")
                    add_fw(FrameworkInfo(name=name, category="frontend" if name == "Vue" else "fullstack", version=ver, manifest_source=str(pkg_path.relative_to(root))))
                if "@angular/core" in deps:
                    add_fw(FrameworkInfo(name="Angular", category="frontend", version=deps["@angular/core"], manifest_source=str(pkg_path.relative_to(root))))
                if "svelte" in deps:
                    add_fw(FrameworkInfo(name="Svelte", category="frontend", version=deps["svelte"], manifest_source=str(pkg_path.relative_to(root))))
                if "express" in deps:
                    add_fw(FrameworkInfo(name="Express", category="backend", version=deps["express"], manifest_source=str(pkg_path.relative_to(root))))
                if "@nestjs/core" in deps:
                    add_fw(FrameworkInfo(name="NestJS", category="backend", version=deps["@nestjs/core"], manifest_source=str(pkg_path.relative_to(root))))
                if "fastify" in deps:
                    add_fw(FrameworkInfo(name="Fastify", category="backend", version=deps["fastify"], manifest_source=str(pkg_path.relative_to(root))))
                if "react-native" in deps:
                    add_fw(FrameworkInfo(name="React Native", category="mobile", version=deps["react-native"], manifest_source=str(pkg_path.relative_to(root))))
                if "electron" in deps:
                    add_fw(FrameworkInfo(name="Electron", category="desktop", version=deps["electron"], manifest_source=str(pkg_path.relative_to(root))))
            except Exception:
                pass

        # 2. Python Frameworks (pyproject.toml, requirements.txt, Pipfile, setup.py)
        python_manifests = ["pyproject.toml", "requirements.txt", "Pipfile", "setup.py", "requirements-dev.txt"]
        for p_name in python_manifests:
            p_file = root / p_name
            if p_file.is_file():
                content = p_file.read_text(encoding="utf-8", errors="ignore").lower()
                if "fastapi" in content:
                    add_fw(FrameworkInfo(name="FastAPI", category="backend", manifest_source=p_name))
                if "django" in content:
                    add_fw(FrameworkInfo(name="Django", category="fullstack", manifest_source=p_name))
                if "flask" in content:
                    add_fw(FrameworkInfo(name="Flask", category="backend", manifest_source=p_name))
                if "tornado" in content:
                    add_fw(FrameworkInfo(name="Tornado", category="backend", manifest_source=p_name))
                if "celery" in content:
                    add_fw(FrameworkInfo(name="Celery", category="backend", manifest_source=p_name))
                if "torch" in content or "pytorch" in content:
                    add_fw(FrameworkInfo(name="PyTorch", category="ml", manifest_source=p_name))
                if "tensorflow" in content:
                    add_fw(FrameworkInfo(name="TensorFlow", category="ml", manifest_source=p_name))

        # 3. Go Frameworks (go.mod)
        go_mod = root / "go.mod"
        if go_mod.is_file():
            content = go_mod.read_text(encoding="utf-8", errors="ignore")
            if "github.com/gin-gonic/gin" in content:
                add_fw(FrameworkInfo(name="Gin", category="backend", manifest_source="go.mod"))
            if "github.com/gofiber/fiber" in content:
                add_fw(FrameworkInfo(name="Fiber", category="backend", manifest_source="go.mod"))
            if "github.com/labstack/echo" in content:
                add_fw(FrameworkInfo(name="Echo", category="backend", manifest_source="go.mod"))
            if "google.golang.org/grpc" in content:
                add_fw(FrameworkInfo(name="gRPC-Go", category="backend", manifest_source="go.mod"))

        # 4. Rust Frameworks (Cargo.toml)
        cargo_toml = root / "Cargo.toml"
        if cargo_toml.is_file():
            content = cargo_toml.read_text(encoding="utf-8", errors="ignore")
            if "actix-web" in content:
                add_fw(FrameworkInfo(name="Actix-web", category="backend", manifest_source="Cargo.toml"))
            if "axum" in content:
                add_fw(FrameworkInfo(name="Axum", category="backend", manifest_source="Cargo.toml"))
            if "rocket" in content:
                add_fw(FrameworkInfo(name="Rocket", category="backend", manifest_source="Cargo.toml"))
            if "tokio" in content:
                add_fw(FrameworkInfo(name="Tokio", category="backend", manifest_source="Cargo.toml"))

        # 5. Java / Kotlin (pom.xml, build.gradle)
        pom_xml = root / "pom.xml"
        if pom_xml.is_file():
            content = pom_xml.read_text(encoding="utf-8", errors="ignore")
            if "spring-boot" in content:
                add_fw(FrameworkInfo(name="Spring Boot", category="backend", manifest_source="pom.xml"))
            elif "org.springframework" in content:
                add_fw(FrameworkInfo(name="Spring", category="backend", manifest_source="pom.xml"))
            if "quarkus" in content:
                add_fw(FrameworkInfo(name="Quarkus", category="backend", manifest_source="pom.xml"))
            if "micronaut" in content:
                add_fw(FrameworkInfo(name="Micronaut", category="backend", manifest_source="pom.xml"))

        gradle_file = root / "build.gradle" or root / "build.gradle.kts"
        if gradle_file.is_file():
            content = gradle_file.read_text(encoding="utf-8", errors="ignore")
            if "spring-boot" in content or "org.springframework.boot" in content:
                add_fw(FrameworkInfo(name="Spring Boot", category="backend", manifest_source="build.gradle"))
            if "com.android.application" in content or "com.android.library" in content:
                add_fw(FrameworkInfo(name="Android SDK", category="mobile", manifest_source="build.gradle"))

        # 6. Flutter / Dart (pubspec.yaml)
        pubspec = root / "pubspec.yaml"
        if pubspec.is_file():
            content = pubspec.read_text(encoding="utf-8", errors="ignore")
            if "flutter:" in content or "sdk: flutter" in content:
                add_fw(FrameworkInfo(name="Flutter", category="mobile", manifest_source="pubspec.yaml"))

        # 7. PHP / Laravel / Symfony (composer.json)
        composer_json = root / "composer.json"
        if composer_json.is_file():
            try:
                data = json.loads(composer_json.read_text(encoding="utf-8", errors="ignore"))
                deps = {**data.get("require", {}), **data.get("require-dev", {})}
                if "laravel/framework" in deps:
                    add_fw(FrameworkInfo(name="Laravel", category="fullstack", version=deps["laravel/framework"], manifest_source="composer.json"))
                if "symfony/framework-bundle" in deps:
                    add_fw(FrameworkInfo(name="Symfony", category="backend", version=deps["symfony/framework-bundle"], manifest_source="composer.json"))
            except Exception:
                pass

        # 8. Ruby on Rails (Gemfile)
        gemfile = root / "Gemfile"
        if gemfile.is_file():
            content = gemfile.read_text(encoding="utf-8", errors="ignore")
            if "rails" in content:
                add_fw(FrameworkInfo(name="Ruby on Rails", category="fullstack", manifest_source="Gemfile"))
            elif "sinatra" in content:
                add_fw(FrameworkInfo(name="Sinatra", category="backend", manifest_source="Gemfile"))

        return detected
