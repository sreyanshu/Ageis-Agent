"""
Aegis Bounded Process Execution Engine
Provides safe, bounded, deterministic subprocess execution with strict timeouts,
output caps, environment sanitization, and dry-run guarantees.
"""

from __future__ import annotations
import os
import time
import subprocess
import signal
from typing import Dict, List, Optional, Sequence
from pydantic import BaseModel, Field

from aegis.core.exceptions import ExecutionError, ExecutionTimeoutError


class ExecutionResult(BaseModel):
    """Encapsulates the deterministic outcome of a command execution."""
    command: List[str]
    cwd: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    timed_out: bool = False
    dry_run: bool = False

    @property
    def is_success(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


class ProcessExecutor:
    """Safe execution substrate for executing commands against arbitrary workspaces."""

    DEFAULT_MAX_OUTPUT_BYTES = 2 * 1024 * 1024  # 2MB buffer cap

    def __init__(
        self,
        default_cwd: Optional[str] = None,
        default_timeout_seconds: int = 120,
        safe_env: bool = True,
        max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES,
    ) -> None:
        self.default_cwd = default_cwd or os.getcwd()
        self.default_timeout_seconds = default_timeout_seconds
        self.safe_env = safe_env
        self.max_output_bytes = max_output_bytes

    def _sanitize_env(self, custom_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Creates a clean, isolated environment dictionary with sensitive tokens scrubbed."""
        env = dict(os.environ)
        
        if self.safe_env:
            # Sensitive keys to redact or isolate from arbitrary target builds if needed
            sensitive_patterns = ["AWS_SECRET", "PRIVATE_KEY", "SSH_AUTH_SOCK", "VAULT_TOKEN"]
            for key in list(env.keys()):
                if any(pat in key.upper() for pat in sensitive_patterns):
                    env.pop(key, None)

        if custom_env:
            env.update(custom_env)

        return env

    def run(
        self,
        command: Sequence[str],
        cwd: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        env: Optional[Dict[str, str]] = None,
        dry_run: bool = False,
    ) -> ExecutionResult:
        """
        Executes a command with strict timeout bounds and output capture.
        """
        cmd_list = [str(c) for c in command]
        target_cwd = cwd or self.default_cwd
        timeout = timeout_seconds if timeout_seconds is not None else self.default_timeout_seconds

        if dry_run:
            return ExecutionResult(
                command=cmd_list,
                cwd=target_cwd,
                exit_code=0,
                stdout=f"[DRY_RUN] Simulated execution: {' '.join(cmd_list)} in {target_cwd}",
                stderr="",
                duration_ms=0.0,
                timed_out=False,
                dry_run=True,
            )

        start_time = time.perf_counter()
        sanitized_env = self._sanitize_env(env)

        timed_out = False
        stdout_text = ""
        stderr_text = ""
        exit_code = -1

        try:
            proc = subprocess.Popen(
                cmd_list,
                cwd=target_cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=sanitized_env,
                text=True,
                encoding="utf-8",
                errors="replace",
                preexec_fn=os.setsid if hasattr(os, "setsid") else None,
            )

            try:
                stdout_text, stderr_text = proc.communicate(timeout=timeout)
                exit_code = proc.returncode
            except subprocess.TimeoutExpired:
                timed_out = True
                # Kill process group safely
                if hasattr(os, "killpg") and hasattr(os, "getpgid"):
                    try:
                        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                else:
                    proc.terminate()

                time.sleep(0.1)
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass

                stdout_text, stderr_text = proc.communicate()
                exit_code = -124  # Standard timeout exit status

        except FileNotFoundError as e:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return ExecutionResult(
                command=cmd_list,
                cwd=target_cwd,
                exit_code=127,
                stdout="",
                stderr=f"Executable not found: {e}",
                duration_ms=duration_ms,
                timed_out=False,
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return ExecutionResult(
                command=cmd_list,
                cwd=target_cwd,
                exit_code=1,
                stdout="",
                stderr=f"Execution failed: {e}",
                duration_ms=duration_ms,
                timed_out=False,
            )

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        # Truncate output buffer if larger than configured threshold to protect memory
        if len(stdout_text.encode("utf-8")) > self.max_output_bytes:
            stdout_text = stdout_text[:self.max_output_bytes] + "\n... [TRUNCATED BY AEGIS EXECUTOR]"
        if len(stderr_text.encode("utf-8")) > self.max_output_bytes:
            stderr_text = stderr_text[:self.max_output_bytes] + "\n... [TRUNCATED BY AEGIS EXECUTOR]"

        return ExecutionResult(
            command=cmd_list,
            cwd=target_cwd,
            exit_code=exit_code,
            stdout=stdout_text,
            stderr=stderr_text,
            duration_ms=duration_ms,
            timed_out=timed_out,
        )
