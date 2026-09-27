"""
Aegis Core Domain Exceptions
"""

class AegisError(Exception):
    """Base class for all Aegis-specific domain exceptions."""
    pass


class ConfigurationError(AegisError):
    """Raised when configuration validation, parsing, or resolution fails."""
    pass


class DiscoveryError(AegisError):
    """Raised when project discovery or static analysis fails."""
    pass


class ExecutionError(AegisError):
    """Raised when process execution or runner invocation fails."""
    pass


class ExecutionTimeoutError(ExecutionError):
    """Raised when an execution exceeds its allocated time boundary."""
    pass


class StorageError(AegisError):
    """Raised when storage I/O, serialization, or artifact management fails."""
    pass


class EvidenceError(AegisError):
    """Raised when evidence collection or verification encounters an invalid state."""
    pass


class NotImplementedCapabilityError(AegisError):
    """Raised explicitly when an interface is defined but implementation is deferred to future phase."""
    pass
