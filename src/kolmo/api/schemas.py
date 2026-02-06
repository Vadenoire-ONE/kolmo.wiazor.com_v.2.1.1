"""
KOLMO API Response Schemas

🔒 REQ-6.3: kolmo_value_str MUST be exact decimal as string with 18 decimals.
🔒 REQ-6.4: kolmo_value (float) MAY be included but marked deprecated.
🔒 REQ-6.5: winner_reason MUST be included for explainability.
"""

from datetime import date as DateType, datetime
from typing import Any

from pydantic import BaseModel, Field

from kolmo.models import KolmoState, WinnerCoin, WinnerReason


class WinnerResponse(BaseModel):
    """
    🔒 REQ-6.2: Response schema for /api/v1/winner/latest and /api/v1/rates/{date}
    """
    date: DateType = Field(
        description="Date of this Winner selection"
    )
    winner: WinnerCoin = Field(
        description="Winning KOLMO coin"
    )
    
    # 🔒 AUTHORITATIVE: Exact decimal as string
    kolmo_value_str: str = Field(
        description=(
            "🔒 AUTHORITATIVE: Exact KOLMO invariant with 18-decimal precision. "
            "Use this value for audit calculations and financial reporting."
        ),
        pattern=r"^\d+\.\d{18}$",
        examples=["1.000041342600000000"]
    )
    
    # 💡 CONVENIENCE: Approximate float (deprecated)
    kolmo_value: float = Field(
        deprecated=True,
        description=(
            "💡 CONVENIENCE ONLY: Approximate float for dashboards/charts. "
            "DO NOT use for financial calculations - use kolmo_value_str instead."
        )
    )
    
    r_me4u: str = Field(description="ME4U rate (USD/CNY)")
    r_iou2: str = Field(description="IOU2 rate (RUB/USD)")
    r_uome: str = Field(description="UOME rate (CNY/RUB)")
    
    kolmo_deviation: float = Field(
        description="Deviation from perfect invariant (|K - 1| * 100)"
    )
    kolmo_state: KolmoState = Field(
        description="OK: deviation < 1%, WARN: 1-5%, CRITICAL: ≥5%"
    )
    
    # 🔒 EXPLAINABILITY
    winner_reason: WinnerReason = Field(
        description="Explainability metadata for winner selection"
    )
    
    # Optional distance metrics
    dist_me4u: float | None = None
    dist_iou2: float | None = None
    dist_uome: float | None = None
    
    relpath_me4u: float | None = None
    relpath_iou2: float | None = None
    relpath_uome: float | None = None
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "date": "2026-01-15",
                "winner": "IOU2",
                "kolmo_value_str": "1.000041342600000000",
                "kolmo_value": 1.000041,
                "r_me4u": "0.143400",
                "r_iou2": "76.550000",
                "r_uome": "0.090966",
                "kolmo_deviation": 0.0041,
                "kolmo_state": "OK",
                "winner_reason": {
                    "me4u_relpath": -0.35,
                    "iou2_relpath": 3.24,
                    "uome_relpath": 0.05,
                    "max_relpath": 3.24,
                    "tied_coins": ["IOU2"],
                    "selection_rule": "max_positive_alphabetical_tiebreak",
                    "winner": "IOU2"
                }
            }
        }
    }


class HealthResponse(BaseModel):
    """
    🔒 REQ-6.8: Health check response for /api/v1/health
    """
    status: str = Field(
        description="Service health status"
    )
    version: str = Field(
        description="API version"
    )
    database: str = Field(
        description="Database connection status"
    )
    latest_data_date: str | None = Field(
        default=None,
        description="Date of most recent KOLMO data"
    )
    data_freshness_hours: float | None = Field(
        default=None,
        description="Hours since latest data"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "healthy",
                "version": "2.1.1",
                "database": "connected",
                "latest_data_date": "2026-01-15",
                "data_freshness_hours": 2.5
            }
        }
    }


class ErrorDetail(BaseModel):
    """Error detail information."""
    code: str = Field(description="Error code")
    message: str = Field(description="Human-readable error message")
    details: dict[str, Any] | None = Field(
        default=None,
        description="Additional error details"
    )
    timestamp: datetime = Field(description="Error timestamp")


class ErrorResponse(BaseModel):
    """
    🔒 REQ-6.9: RFC 7807 Problem Details format
    """
    error: ErrorDetail
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "error": {
                    "code": "KOLMO_DATA_NOT_FOUND",
                    "message": "No KOLMO data available for date 2026-01-16",
                    "details": {
                        "requested_date": "2026-01-16",
                        "latest_available": "2026-01-15"
                    },
                    "timestamp": "2026-01-15T15:30:00Z"
                }
            }
        }
    }
