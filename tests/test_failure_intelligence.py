"""
Unit Tests for Aegis Failure Intelligence, Redaction, and Classification
"""

from pathlib import Path
from aegis.history.failures import FailureClassifier, FailureIntelligenceEngine
from aegis.history.models import FailureCategory, FailureStatus
from aegis.history.store import HistoryStore


def test_failure_normalization_and_secret_redaction():
    raw_error = (
        "AssertionError at 0x7fff5bfc in /private/var/folders/v8/tmp_123/test.py:42: "
        "User password='super_secret_password_123' token: 'eyJhG...xxx' failed at 2026-09-27 17:00:00 "
        "connecting to localhost:54321 with session 12345678-1234-1234-1234-123456789abc"
    )
    normalized = FailureClassifier.normalize_message(raw_error)

    assert "super_secret_password_123" not in normalized
    assert "<REDACTED_SECRET>" in normalized
    assert "<HEX_ADDR>" in normalized
    assert "<TMP_PATH>" in normalized
    assert "<TIMESTAMP>" in normalized
    assert "localhost:<PORT>" in normalized
    assert "<UUID>" in normalized


def test_deterministic_failure_classification():
    # 1. Product defect
    cat, conf, _ = FailureClassifier.classify("AssertionError", "Expected status code 200, got 500")
    assert cat == FailureCategory.PRODUCT_DEFECT
    assert conf >= 0.8

    # 2. Timeout
    cat_t, conf_t, _ = FailureClassifier.classify("TimeoutError", "Execution timed out after 30 seconds")
    assert cat_t == FailureCategory.TIMEOUT
    assert conf_t >= 0.9

    # 3. Infrastructure
    cat_i, conf_i, _ = FailureClassifier.classify("RunnerError", "Docker container runner unavailable: executable not found")
    assert cat_i == FailureCategory.INFRASTRUCTURE
    assert conf_i >= 0.85

    # 4. Dependency
    cat_d, conf_d, _ = FailureClassifier.classify("ModuleNotFoundError", "No module named 'fastapi'")
    assert cat_d == FailureCategory.DEPENDENCY


def test_failure_clustering_lifecycle(tmp_path: Path):
    store = HistoryStore(tmp_path / "history")
    engine = FailureIntelligenceEngine(store)

    # 1. New failure
    c1 = engine.process_failure(
        test_id="test_payment",
        exception_type="AssertionError",
        message="Total amount mismatch at 0x1234",
    )
    assert c1.status == FailureStatus.NEW_FAILURE
    assert c1.occurrences == 1

    # 2. Recurring failure with different volatile memory address
    c2 = engine.process_failure(
        test_id="test_payment",
        exception_type="AssertionError",
        message="Total amount mismatch at 0x9999",  # Different hex address, same normalized fingerprint!
    )
    assert c2.fingerprint == c1.fingerprint
    assert c2.status == FailureStatus.RECURRING_FAILURE
    assert c2.occurrences == 2

    # 3. Mark resolved
    resolved = engine.mark_resolved(c1.fingerprint)
    assert resolved is True

    # 4. Regressed failure
    c3 = engine.process_failure(
        test_id="test_payment",
        exception_type="AssertionError",
        message="Total amount mismatch at 0xaaaa",
    )
    assert c3.status == FailureStatus.REGRESSED_FAILURE
