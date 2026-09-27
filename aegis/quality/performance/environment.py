"""
Aegis Deterministic Performance Environment Fingerprinting
Captures hardware, OS, runtime, and architecture metadata to ensure valid baseline comparisons.
"""

from __future__ import annotations
import os
import sys
import platform
import hashlib
import shutil
import subprocess
from typing import Dict, Any


class EnvironmentFingerprint:
    """Captures and compares deterministic runtime environments."""

    @classmethod
    def capture(cls, tree_hash: str = "") -> Dict[str, Any]:
        """Captures hardware and runtime attributes."""
        info = {
            "os_name": platform.system(),
            "os_release": platform.release(),
            "machine_arch": platform.machine(),
            "cpu_count": os.cpu_count() or 1,
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "node_version": cls._get_node_version(),
            "tree_hash": tree_hash,
        }
        raw_sig = f"{info['os_name']}:{info['machine_arch']}:{info['cpu_count']}:{info['python_version']}"
        info["fingerprint_hash"] = f"env_{hashlib.sha256(raw_sig.encode('utf-8')).hexdigest()[:16]}"
        return info

    @staticmethod
    def _get_node_version() -> str:
        if not shutil.which("node"):
            return "none"
        try:
            res = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=2)
            return res.stdout.strip()
        except Exception:
            return "none"

    @classmethod
    def are_compatible(cls, env1: Dict[str, Any], env2: Dict[str, Any]) -> bool:
        """Determines if two environments are comparable for performance regression."""
        if not env1 or not env2:
            return False
        # OS, architecture, and major python version must match
        if env1.get("os_name") != env2.get("os_name"):
            return False
        if env1.get("machine_arch") != env2.get("machine_arch"):
            return False
        py1 = env1.get("python_version", "").split(".")[0]
        py2 = env2.get("python_version", "").split(".")[0]
        if py1 != py2:
            return False
        return True
