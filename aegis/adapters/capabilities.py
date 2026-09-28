"""
Aegis Universal Capability Model
Defines the standard capability abstractions, statuses, and evidence models
for universal repository onboarding and technology discovery.
"""

from __future__ import annotations
import time
from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class CapabilityType(str, Enum):
    """Universal software engineering capability dimensions."""
    LANGUAGE = "LANGUAGE"
    FRAMEWORK = "FRAMEWORK"
    BUILD = "BUILD"
    TEST_UNIT = "TEST_UNIT"
    TEST_API = "TEST_API"
    TEST_INTEGRATION = "TEST_INTEGRATION"
    TEST_E2E = "TEST_E2E"
    TEST_UI = "TEST_UI"
    TEST_MOBILE = "TEST_MOBILE"
    BROWSER = "BROWSER"
    API = "API"
    DATABASE = "DATABASE"
    CACHE = "CACHE"
    QUEUE = "QUEUE"
    SECURITY = "SECURITY"
    ACCESSIBILITY = "ACCESSIBILITY"
    PERFORMANCE = "PERFORMANCE"
    CONTAINER = "CONTAINER"
    CI = "CI"
    DEPLOYMENT = "DEPLOYMENT"
    OBSERVABILITY = "OBSERVABILITY"


class CapabilityStatus(str, Enum):
    """Operational status of a capability within the project."""
    DETECTED = "DETECTED"
    SUPPORTED = "SUPPORTED"
    CONFIGURED = "CONFIGURED"
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"


class ProjectCapability(BaseModel):
    """A verified capability discovered in the software project with evidence provenance."""
    id: str
    type: CapabilityType
    name: str
    status: CapabilityStatus = CapabilityStatus.DETECTED
    confidence: float = 1.0          # 0.0 to 1.0 deterministic confidence
    evidence: List[str] = Field(default_factory=list)
    source: str = "discovery"        # file, import, config, scanner
    discovered_at: float = Field(default_factory=time.time)
    metadata: Dict[str, Any] = Field(default_factory=dict)
