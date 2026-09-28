"""
Aegis Testing Adapters (Pytest, Vitest/Jest, Go Test, Playwright)
Discovers test framework configurations, maps tests to universal models, and declares testing capabilities.
"""

from __future__ import annotations
import os
import re
from pathlib import Path
from typing import List, Dict, Any

from aegis.adapters.base import AegisAdapter, DetectionResult, DiscoveryResult, ValidationResult
from aegis.adapters.capabilities import ProjectCapability, CapabilityType, CapabilityStatus
from aegis.discovery.tests import TestDetector, TestSuiteInfo


class PytestTestAdapter(AegisAdapter):
    """Adapter for Pytest test framework and test discovery."""

    def __init__(self) -> None:
        super().__init__(
            adapter_id="test_pytest",
            name="Pytest Test Adapter",
            category="testing",
            version="1.0.0",
        )
        self.detector = TestDetector()

    def detect(self, workspace_root: Path) -> DetectionResult:
        evidence = []
        suites = self.detector.detect(workspace_root)
        py_suite = next((s for s in suites if s.framework == "pytest"), None)

        if (workspace_root / "pytest.ini").is_file():
            evidence.append("Found pytest.ini configuration")
        if (workspace_root / "conftest.py").is_file():
            evidence.append("Found root conftest.py fixture definition")
        pyproject = workspace_root / "pyproject.toml"
        if pyproject.is_file() and "[tool.pytest" in pyproject.read_text():
            evidence.append("Found [tool.pytest] configuration in pyproject.toml")

        if py_suite and py_suite.test_files:
            evidence.append(f"Discovered {len(py_suite.test_files)} Python test files ({py_suite.test_count_estimate} test cases)")

        detected = py_suite is not None or len(evidence) > 0
        return DetectionResult(
            detected=detected,
            confidence=1.0 if len(evidence) >= 2 else (0.85 if detected else 0.0),
            evidence=evidence,
            metadata={"test_count": py_suite.test_count_estimate if py_suite else 0},
        )

    def capabilities(self, workspace_root: Path) -> List[ProjectCapability]:
        det = self.detect(workspace_root)
        if not det.detected:
            return []
        return [
            ProjectCapability(
                id="cap_test_unit_pytest",
                type=CapabilityType.TEST_UNIT,
                name="Pytest Unit Testing",
                status=CapabilityStatus.AVAILABLE,
                confidence=det.confidence,
                evidence=det.evidence,
                source="PytestTestAdapter",
            ),
            ProjectCapability(
                id="cap_test_integration_pytest",
                type=CapabilityType.TEST_INTEGRATION,
                name="Pytest Integration Testing",
                status=CapabilityStatus.AVAILABLE,
                confidence=det.confidence,
                evidence=det.evidence,
                source="PytestTestAdapter",
            ),
        ]

    def discover(self, workspace_root: Path) -> DiscoveryResult:
        caps = self.capabilities(workspace_root)
        suites = self.detector.detect(workspace_root)
        py_suites = [s for s in suites if s.framework == "pytest"]
        configs = []
        for name in ("pytest.ini", "conftest.py", "pyproject.toml", "tox.ini"):
            if (workspace_root / name).is_file():
                configs.append(name)
        return DiscoveryResult(
            capabilities=caps,
            configuration_files=configs,
            test_suites=py_suites,
            metadata={"total_pytest_suites": len(py_suites)},
        )


class VitestJestAdapter(AegisAdapter):
    """Adapter for JavaScript / TypeScript test runners (Vitest, Jest)."""

    def __init__(self) -> None:
        super().__init__(
            adapter_id="test_vitest_jest",
            name="Vitest / Jest Test Adapter",
            category="testing",
            version="1.0.0",
        )
        self.detector = TestDetector()

    def detect(self, workspace_root: Path) -> DetectionResult:
        evidence = []
        suites = self.detector.detect(workspace_root)
        js_suite = next((s for s in suites if s.framework in ("vitest", "jest")), None)

        for fname in ("vitest.config.ts", "vitest.config.js", "jest.config.js", "jest.config.ts", "jest.config.json"):
            if (workspace_root / fname).is_file():
                evidence.append(f"Found test runner configuration: {fname}")

        if js_suite and js_suite.test_files:
            evidence.append(f"Discovered {len(js_suite.test_files)} JS/TS test files ({js_suite.test_count_estimate} test cases)")

        detected = js_suite is not None or len(evidence) > 0
        return DetectionResult(
            detected=detected,
            confidence=1.0 if len(evidence) >= 2 else (0.85 if detected else 0.0),
            evidence=evidence,
            metadata={"runner": js_suite.framework if js_suite else "jest"},
        )

    def capabilities(self, workspace_root: Path) -> List[ProjectCapability]:
        det = self.detect(workspace_root)
        if not det.detected:
            return []
        runner = det.metadata.get("runner", "vitest/jest").capitalize()
        return [
            ProjectCapability(
                id="cap_test_unit_js",
                type=CapabilityType.TEST_UNIT,
                name=f"{runner} Unit Testing",
                status=CapabilityStatus.AVAILABLE,
                confidence=det.confidence,
                evidence=det.evidence,
                source="VitestJestAdapter",
            ),
            ProjectCapability(
                id="cap_test_ui_js",
                type=CapabilityType.TEST_UI,
                name=f"{runner} Component Testing",
                status=CapabilityStatus.AVAILABLE,
                confidence=det.confidence,
                evidence=det.evidence,
                source="VitestJestAdapter",
            ),
        ]

    def discover(self, workspace_root: Path) -> DiscoveryResult:
        caps = self.capabilities(workspace_root)
        suites = self.detector.detect(workspace_root)
        js_suites = [s for s in suites if s.framework in ("vitest", "jest")]
        configs = []
        for name in ("vitest.config.ts", "vitest.config.js", "jest.config.js", "jest.config.ts"):
            if (workspace_root / name).is_file():
                configs.append(name)
        return DiscoveryResult(
            capabilities=caps,
            configuration_files=configs,
            test_suites=js_suites,
        )


class GoTestAdapter(AegisAdapter):
    """Adapter for Go standard test runner."""

    def __init__(self) -> None:
        super().__init__(
            adapter_id="test_gotest",
            name="Go Test Adapter",
            category="testing",
            version="1.0.0",
        )
        self.detector = TestDetector()

    def detect(self, workspace_root: Path) -> DetectionResult:
        evidence = []
        suites = self.detector.detect(workspace_root)
        go_suite = next((s for s in suites if s.framework == "go test"), None)

        if go_suite and go_suite.test_files:
            evidence.append(f"Discovered {len(go_suite.test_files)} Go test files ({go_suite.test_count_estimate} test functions)")

        detected = go_suite is not None and len(go_suite.test_files) > 0
        return DetectionResult(
            detected=detected,
            confidence=1.0 if detected else 0.0,
            evidence=evidence,
        )

    def capabilities(self, workspace_root: Path) -> List[ProjectCapability]:
        det = self.detect(workspace_root)
        if not det.detected:
            return []
        return [
            ProjectCapability(
                id="cap_test_unit_gotest",
                type=CapabilityType.TEST_UNIT,
                name="Go Unit & Integration Testing",
                status=CapabilityStatus.AVAILABLE,
                confidence=det.confidence,
                evidence=det.evidence,
                source="GoTestAdapter",
            )
        ]

    def discover(self, workspace_root: Path) -> DiscoveryResult:
        caps = self.capabilities(workspace_root)
        suites = self.detector.detect(workspace_root)
        go_suites = [s for s in suites if s.framework == "go test"]
        return DiscoveryResult(capabilities=caps, configuration_files=[], test_suites=go_suites)
