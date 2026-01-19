"""
KOLMO API Module

🔒 NORMATIVE: REST API follows Technical Specification v.2.1.1 Section 6
"""

from kolmo.api.routes import router
from kolmo.api.schemas import (
    WinnerResponse,
    HealthResponse,
    ErrorResponse,
)

__all__ = [
    "router",
    "WinnerResponse",
    "HealthResponse",
    "ErrorResponse",
]
