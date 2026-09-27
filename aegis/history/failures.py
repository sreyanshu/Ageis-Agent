"""
Aegis Failure Intelligence & Classification Engine
Normalizes volatile error noise, redacts secrets, classifies failure root cause, and clusters fingerprints.
"""

from __future__ import annotations
import re
import hashlib
import time
from typing import Dict, Any, List, Optional, Tuple

from aegis.history.models import (
    FailureCategory,
    FailureStatus,
    FailureCluster,
)
from aegis.history.store import HistoryStore


class FailureClassifier:
    """Deterministic classifier categorizing failures based on error patterns and stack context."""

    _SECRET_PATTERNS = [
        (re.compile(r'(?i)(password|secret|token|api_?key|auth_?token|bearer)\s*[:=]\s*[\'"][^\'"]+[\'"]'), r'\1: <REDACTED_SECRET>'),
        (re.compile(r'(?i)(token|key|secret)\s+(sk_[a-zA-Z0-9_]+|[a-zA-Z0-9_\-]{24,})'), r'\1 <REDACTED_SECRET>'),
        (re.compile(r'ghp_[a-zA-Z0-9]{36}'), '<REDACTED_TOKEN>'),
        (re.compile(r'sk_(live|test)_[a-zA-Z0-9]+'), '<REDACTED_API_KEY>'),
        (re.compile(r'ey[a-zA-Z0-9_\-]{20,}\.[a-zA-Z0-9_\-]{20,}\.[a-zA-Z0-9_\-]{10,}'), '<REDACTED_JWT>'),
    ]

    _VOLATILE_PATTERNS = [
        (re.compile(r'0x[0-9a-fA-F]+'), '<HEX_ADDR>'),
        (re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'), '<UUID>'),
        (re.compile(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?'), '<TIMESTAMP>'),
        (re.compile(r'(?:/private)?/var/folders/[^\s\'":]+'), '<TMP_PATH>'),
        (re.compile(r'/tmp/[^\s\'":]+'), '<TMP_PATH>'),
        (re.compile(r'(localhost|127\.0\.0\.1):\d{4,5}'), r'\1:<PORT>'),
    ]

    @classmethod
    def redact_secrets(cls, text: str) -> str:
        """Removes secrets and sensitive tokens from error messages."""
        if not text:
            return ""
        out = text
        for pat, repl in cls._SECRET_PATTERNS:
            out = pat.sub(repl, out)
        return out

    @classmethod
    def normalize_message(cls, message: str) -> str:
        """Strips volatile runtime noise (memory addresses, temp paths, timestamps, UUIDs, dynamic ports)."""
        if not message:
            return ""
        sanitized = cls.redact_secrets(message.strip())
        for pat, replacement in cls._VOLATILE_PATTERNS:
            sanitized = pat.sub(replacement, sanitized)
        return sanitized

    @classmethod
    def compute_fingerprint(
        cls,
        exception_type: str,
        message: str,
        top_stack_frame: Optional[str] = None,
        test_id: Optional[str] = None,
    ) -> str:
        """Generates deterministic failure fingerprint."""
        norm_type = (exception_type or "UnknownError").strip()
        norm_msg = cls.normalize_message(message)
        norm_frame = cls.normalize_message(top_stack_frame or "")
        raw = f"{norm_type}:{norm_msg}:{norm_frame}"
        return f"fp_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"

    @classmethod
    def classify(cls, exception_type: str, message: str, raw_stderr: Optional[str] = None) -> Tuple[FailureCategory, float, str]:
        """
        Classifies failure into deterministic category with confidence score and reason.
        """
        full_text = f"{exception_type} {message} {raw_stderr or ''}".lower()

        if any(w in full_text for w in ["timeout", "timed out", "deadlineexceeded", "timedout"]):
            return FailureCategory.TIMEOUT, 0.95, "Execution exceeded allocated time limit."

        if any(w in full_text for w in ["connection refused", "econnrefused", "nosock", "dns", "getaddrinfo", "network unreachable"]):
            return FailureCategory.NETWORK, 0.92, "Network connection refused or socket unreachable."

        if any(w in full_text for w in ["docker", "container", "runner unavailable", "command not found", "executable not found", "sigkill", "sigterm"]):
            return FailureCategory.INFRASTRUCTURE, 0.90, "Underlying runner binary or infrastructure dependency unavailable."

        if any(w in full_text for w in ["nosuchfile", "filenotfound", "importerror", "modulenotfounderror", "package not found"]):
            return FailureCategory.DEPENDENCY, 0.88, "Missing module, package dependency, or file resource."

        if any(w in full_text for w in ["assert", "assertionerror", "expect(", "status code 500", "schema validation error", "mismatch"]):
            return FailureCategory.PRODUCT_DEFECT, 0.85, "Assertion failure in validated application logic or contract."

        if any(w in full_text for w in ["syntaxerror", "nameerror", "attributeerror: 'nonetype'"]):
            return FailureCategory.TEST_DEFECT, 0.80, "Defect or unhandled exception in test implementation."

        if any(w in full_text for w in ["config", "missing environment variable", "env var"]):
            return FailureCategory.CONFIGURATION, 0.85, "Invalid or missing configuration parameters."

        return FailureCategory.UNKNOWN, 0.50, "Unclassified failure signature."


class FailureIntelligenceEngine:
    """Manages failure fingerprint clustering, recurring failure tracking, and resolution states."""

    def __init__(self, store: HistoryStore) -> None:
        self.store = store

    def process_failure(
        self,
        test_id: str,
        exception_type: str,
        message: str,
        top_stack_frame: Optional[str] = None,
        raw_stderr: Optional[str] = None,
        environment: str = "default",
    ) -> FailureCluster:
        """
        Processes a raw failure, clusters it against history, and updates occurrence metrics.
        """
        norm_msg = FailureClassifier.normalize_message(message)
        fp = FailureClassifier.compute_fingerprint(exception_type, message, top_stack_frame, test_id)
        cat, conf, reason = FailureClassifier.classify(exception_type, message, raw_stderr)

        existing_clusters = {c.fingerprint: c for c in self.store.get_failure_clusters(limit=500)}
        now = time.time()

        if fp in existing_clusters:
            cluster = existing_clusters[fp]
            cluster.last_seen = now
            cluster.occurrences += 1
            if cluster.status == FailureStatus.RESOLVED_FAILURE:
                cluster.status = FailureStatus.REGRESSED_FAILURE
                cluster.resolved_at = None
            else:
                cluster.status = FailureStatus.RECURRING_FAILURE
            if test_id not in cluster.affected_tests:
                cluster.affected_tests.append(test_id)
            if environment not in cluster.environments:
                cluster.environments.append(environment)
        else:
            cluster = FailureCluster(
                fingerprint=fp,
                first_seen=now,
                last_seen=now,
                occurrences=1,
                status=FailureStatus.NEW_FAILURE,
                classification=cat,
                confidence=conf,
                affected_tests=[test_id],
                environments=[environment],
                sample_message=norm_msg[:300],
                sample_stack_frame=top_stack_frame,
            )

        self.store.save_failure_cluster(cluster)
        return cluster

    def mark_resolved(self, fingerprint: str) -> bool:
        """Marks a failure cluster as resolved."""
        clusters = {c.fingerprint: c for c in self.store.get_failure_clusters(limit=500)}
        if fingerprint in clusters:
            cluster = clusters[fingerprint]
            cluster.status = FailureStatus.RESOLVED_FAILURE
            cluster.resolved_at = time.time()
            self.store.save_failure_cluster(cluster)
            return True
        return False
