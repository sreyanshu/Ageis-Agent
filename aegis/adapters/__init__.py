"""
Aegis Adapters Module
Exports universal adapter contracts, capability models, and central registry.
"""

from aegis.adapters.capabilities import (
    CapabilityType,
    CapabilityStatus,
    ProjectCapability,
)
from aegis.adapters.base import (
    BaseRunner,
    RunnerCapability,
    BaseAdapter,
    DetectionResult,
    DiscoveryResult,
    ValidationResult,
    AegisAdapter,
)
from aegis.adapters.registry import (
    AdapterRegistry,
    default_adapter_registry,
)

__all__ = [
    "CapabilityType",
    "CapabilityStatus",
    "ProjectCapability",
    "BaseRunner",
    "RunnerCapability",
    "BaseAdapter",
    "DetectionResult",
    "DiscoveryResult",
    "ValidationResult",
    "AegisAdapter",
    "AdapterRegistry",
    "default_adapter_registry",
]
