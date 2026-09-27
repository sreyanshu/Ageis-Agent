import sys
from pathlib import Path
from aegis.core.executor import ProcessExecutor


def test_executor_success():
    executor = ProcessExecutor()
    res = executor.run([sys.executable, "-c", "print('Aegis Execution OK')"])
    assert res.is_success is True
    assert res.exit_code == 0
    assert "Aegis Execution OK" in res.stdout
    assert res.duration_ms > 0


def test_executor_dry_run():
    executor = ProcessExecutor()
    res = executor.run(["rm", "-rf", "/nonexistent"], dry_run=True)
    assert res.is_success is True
    assert res.dry_run is True
    assert "[DRY_RUN]" in res.stdout


def test_executor_timeout():
    executor = ProcessExecutor(default_timeout_seconds=1)
    res = executor.run([sys.executable, "-c", "import time; time.sleep(3)"], timeout_seconds=1)
    assert res.timed_out is True
    assert res.is_success is False
    assert res.exit_code == -124


def test_executor_nonexistent_command():
    executor = ProcessExecutor()
    res = executor.run(["aegis_nonexistent_binary_xyz"])
    assert res.exit_code == 127
    assert res.is_success is False
