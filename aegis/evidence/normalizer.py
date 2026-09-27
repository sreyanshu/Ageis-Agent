"""
Aegis Failure Normalizer & Fingerprinting Engine
Normalizes stack traces and error logs, stripping dynamic variables (pointers, timestamps, line variances),
and computes deterministic SHA-256 fingerprints for deduplication and historical lookup.
"""

from __future__ import annotations
import hashlib
import re
from typing import Optional, Tuple
from aegis.evidence.models import NormalizedError


class FailureNormalizer:
    """Normalizes raw error text and produces deterministic fingerprints."""

    # Regex patterns for stripping volatile tokens
    MEMORY_ADDR_REGEX = re.compile(r'0x[0-9a-fA-F]+')
    TIMESTAMP_REGEX = re.compile(r'\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?')
    UUID_REGEX = re.compile(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}')
    TEMP_PATH_REGEX = re.compile(r'/tmp/[A-Za-z0-9_\-\./]+')

    @classmethod
    def sanitize_text(cls, text: str) -> str:
        """Removes volatile tokens like memory addresses, timestamps, UUIDs, and temp paths."""
        if not text:
            return ""
        s = cls.MEMORY_ADDR_REGEX.sub("<HEX_ADDR>", text)
        s = cls.TIMESTAMP_REGEX.sub("<TIMESTAMP>", s)
        s = cls.UUID_REGEX.sub("<UUID>", s)
        s = cls.TEMP_PATH_REGEX.sub("<TEMP_PATH>", s)
        return s.strip()

    @classmethod
    def extract_python_traceback_frame(cls, stderr: str) -> Tuple[str, str, Optional[str]]:
        """
        Extracts exception type, message, and top stack frame from Python tracebacks.
        """
        lines = stderr.strip().splitlines()
        if not lines:
            return "UnknownError", "No output provided", None

        # Last line typically contains 'ExceptionClass: message'
        last_line = lines[-1].strip()
        exc_type = "Error"
        exc_msg = last_line

        if ":" in last_line:
            parts = last_line.split(":", 1)
            exc_type = parts[0].strip()
            exc_msg = parts[1].strip()

        # Find top or innermost file frame: File "...", line X, in Y
        top_frame = None
        for line in reversed(lines):
            line_str = line.strip()
            if line_str.startswith("File ") and "line " in line_str:
                top_frame = line_str
                break

        return exc_type, exc_msg, top_frame

    @classmethod
    def normalize_failure(
        cls,
        raw_error: str,
        category: str = "generic",
        top_frame: Optional[str] = None,
    ) -> NormalizedError:
        """Constructs a normalized error and computes its deterministic SHA-256 fingerprint."""
        sanitized = cls.sanitize_text(raw_error)
        
        # If no explicit frame given, attempt Python traceback parsing
        if not top_frame and ("Traceback (most recent call last)" in raw_error or "File " in raw_error):
            exc_type, exc_msg, extracted_frame = cls.extract_python_traceback_frame(raw_error)
            sanitized_msg = cls.sanitize_text(exc_msg)
            frame_clean = cls.sanitize_text(extracted_frame) if extracted_frame else None
        else:
            exc_type = category
            sanitized_msg = sanitized.splitlines()[0] if sanitized else "Execution error"
            frame_clean = cls.sanitize_text(top_frame) if top_frame else None

        # Deterministic fingerprint formula
        fingerprint_input = f"{exc_type}::{sanitized_msg}::{frame_clean or ''}"
        fp = "fp_" + hashlib.sha256(fingerprint_input.encode("utf-8")).hexdigest()[:32]

        return NormalizedError(
            exception_type=exc_type,
            message=sanitized_msg,
            top_stack_frame=frame_clean,
            fingerprint=fp,
        )
