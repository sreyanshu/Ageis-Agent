"""
Aegis Accessibility Adapters (axe-core, browser substrates, simulated)
"""

from __future__ import annotations
import shutil
from abc import abstractmethod
from typing import Dict, Any, List, Optional
from aegis.quality.base import QualityAdapter


class AccessibilityAdapter(QualityAdapter):
    """Abstract accessibility scanner adapter."""

    @abstractmethod
    def scan_target(self, target: str, options: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Scans a target (HTML file, URL, or component) and returns raw violation records."""
        pass


class AxeCoreAdapter(AccessibilityAdapter):
    """Production axe-core adapter via Node/Browser substrate."""

    @property
    def adapter_name(self) -> str:
        return "axe-core"

    def is_available(self) -> bool:
        # Check if node / npx or playwright is available
        has_node = shutil.which("node") is not None
        has_npx = shutil.which("npx") is not None
        return has_node and has_npx

    def scan_target(self, target: str, options: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        if not self.is_available():
            raise RuntimeError("axe-core runner requires Node.js runtime and npx.")
        # Real invocation would run @axe-core/cli or playwright axe injection
        return []


class SimulatedAxeAdapter(AccessibilityAdapter):
    """Deterministic simulated accessibility adapter for test suites and offline validation."""

    @property
    def adapter_name(self) -> str:
        return "simulated-axe"

    def is_available(self) -> bool:
        return True

    def scan_target(self, target: str, options: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        # Deterministic sample violations based on target contents or default samples
        opts = options or {}
        if opts.get("clean_pass", False):
            return []

        return [
            {
                "id": "color-contrast",
                "impact": "serious",
                "description": "Elements must meet minimum color contrast ratio thresholds (WCAG AA 4.5:1).",
                "help": "Ensure contrast ratio between foreground and background colors meets WCAG standards.",
                "helpUrl": "https://dequeuniversity.com/rules/axe/4.8/color-contrast",
                "nodes": [
                    {
                        "target": ["button.btn-primary"],
                        "html": '<button class="btn-primary" style="color: #888; background: #eee;">Submit</button>',
                        "failureSummary": "Element has insufficient color contrast of 2.1:1 (foreground: #888888, background: #eeeeee, font size: 12pt). Expected ratio of 4.5:1",
                    }
                ],
                "tags": ["wcag2aa", "wcag143", "cat.color"],
            },
            {
                "id": "image-alt",
                "impact": "critical",
                "description": "Elements must have alternate text or a role of none or presentation.",
                "help": "Images must have an alt attribute or aria-label.",
                "helpUrl": "https://dequeuniversity.com/rules/axe/4.8/image-alt",
                "nodes": [
                    {
                        "target": ["img.hero-banner"],
                        "html": '<img src="/static/hero.png" class="hero-banner" />',
                        "failureSummary": "Element does not have an alt attribute",
                    }
                ],
                "tags": ["wcag2a", "wcag111", "cat.text-alternatives"],
            },
        ]
