from pathlib import Path
from aegis.evidence.models import TestResult, TestStatus
from aegis.evidence.normalizer import FailureNormalizer
from aegis.evidence.collector import EvidenceCollector
from aegis.storage.filesystem import FilesystemStorage


def test_failure_normalizer():
    raw_trace = """
Traceback (most recent call last):
  File "/workspace/app/auth.py", line 42, in login
    raise ValueError("Token 0x7ffd12ab expired at 2026-09-27T16:00:00Z for user 550e8400-e29b-41d4-a716-446655440000")
ValueError: Token 0x7ffd12ab expired at 2026-09-27T16:00:00Z for user 550e8400-e29b-41d4-a716-446655440000
    """
    normalized = FailureNormalizer.normalize_failure(raw_trace, category="unit")
    assert normalized.exception_type == "ValueError"
    assert "<HEX_ADDR>" in normalized.message
    assert "<TIMESTAMP>" in normalized.message
    assert "<UUID>" in normalized.message
    assert normalized.fingerprint.startswith("fp_")

    # Identical structure with different address / timestamp generates identical fingerprint
    raw_trace_diff_time = raw_trace.replace("2026-09-27T16:00:00Z", "2026-09-28T09:15:30Z").replace("0x7ffd12ab", "0x3344bbaa")
    norm2 = FailureNormalizer.normalize_failure(raw_trace_diff_time, category="unit")
    assert normalized.fingerprint == norm2.fingerprint


def test_evidence_collector(tmp_path: Path):
    storage = FilesystemStorage(workspace_root=tmp_path)
    collector = EvidenceCollector(project_name="test-proj", storage=storage)

    res1 = TestResult(
        test_id="unit.test_auth_ok",
        name="Test Auth OK",
        category="unit",
        status=TestStatus.PASSED,
        duration_ms=45.0,
    )
    res2 = TestResult(
        test_id="unit.test_auth_fail",
        name="Test Auth Fail",
        category="unit",
        status=TestStatus.FAILED,
        duration_ms=50.0,
        raw_stderr="AssertionError: Expected 200, got 500",
    )

    collector.record_result(res1)
    collector.record_result(res2)

    report = collector.generate_report(tree_hash="abc123hash")
    assert report.total_tests == 2
    assert report.passed == 1
    assert report.failed == 1
    assert len(report.failure_fingerprints) == 1

    # Verify report saved to storage
    assert (tmp_path / ".aegis" / "report.json").exists()
