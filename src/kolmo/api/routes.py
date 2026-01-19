"""
KOLMO API Routes

🔒 REQ-6.1: API base URL: /api/v1/
🔒 REQ-6.6: Response time MUST be < 100ms at P95
"""

import logging
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status

from kolmo import __version__
from kolmo.api.schemas import (
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    WinnerResponse,
)
from kolmo.database import check_connection, get_connection, get_latest_data_date
from kolmo.models import KolmoState, WinnerCoin, WinnerReason, SelectionRule

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["KOLMO"])


def _format_decimal_18(value: Decimal) -> str:
    """
    🔒 REQ-6.3: Format decimal to exactly 18 decimal places.
    """
    return f"{value:.18f}"


def _format_decimal_6(value: Decimal) -> str:
    """Format decimal to 6 decimal places for rates."""
    return f"{value:.6f}"


@router.get(
    "/winner/latest",
    response_model=WinnerResponse,
    summary="Get latest Winner coin",
    description="Returns the most recent winning KOLMO coin for clearing path optimization",
    responses={
        404: {"model": ErrorResponse, "description": "No data available"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    }
)
async def get_winner_latest() -> WinnerResponse:
    """
    🔒 REQ-1.4 & REQ-6.2: GET /api/v1/winner/latest endpoint.
    
    Returns today's winning KOLMO coin for M0.1 integration.
    """
    try:
        async with get_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT 
                    date, winner, r_me4u, r_iou2, r_uome,
                    kolmo_value, kolmo_deviation, kolmo_state,
                    dist_me4u, dist_iou2, dist_uome,
                    relpath_me4u, relpath_iou2, relpath_uome,
                    winner_reason
                FROM mcol1_compute_data
                ORDER BY date DESC
                LIMIT 1
                """
            )
        
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "KOLMO_NO_DATA",
                        "message": "No KOLMO data available",
                        "details": None,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                }
            )
        
        return _row_to_response(row)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching latest winner: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "KOLMO_INTERNAL_ERROR",
                    "message": "Failed to fetch latest winner",
                    "details": None,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
        )


@router.get(
    "/rates/{date}",
    response_model=WinnerResponse,
    summary="Get KOLMO metrics for specific date",
    description="Retrieve KOLMO metrics for a specific historical date",
    responses={
        404: {"model": ErrorResponse, "description": "No data for date"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    }
)
async def get_rates_by_date(date: date) -> WinnerResponse:
    """
    🔒 REQ-6.7: GET /api/v1/rates/{date} endpoint.
    
    Args:
        date: ISO 8601 date (YYYY-MM-DD)
    """
    try:
        async with get_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT 
                    date, winner, r_me4u, r_iou2, r_uome,
                    kolmo_value, kolmo_deviation, kolmo_state,
                    dist_me4u, dist_iou2, dist_uome,
                    relpath_me4u, relpath_iou2, relpath_uome,
                    winner_reason
                FROM mcol1_compute_data
                WHERE date = $1
                """,
                date
            )
        
        if not row:
            # Get latest available date for error message
            latest = await get_latest_data_date()
            
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": "KOLMO_DATA_NOT_FOUND",
                        "message": f"No KOLMO data available for date {date}",
                        "details": {
                            "requested_date": str(date),
                            "latest_available": latest
                        },
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                }
            )
        
        return _row_to_response(row)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching rates for {date}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "KOLMO_INTERNAL_ERROR",
                    "message": f"Failed to fetch rates for {date}",
                    "details": None,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
        )


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Health check for load balancers and monitoring",
    responses={
        503: {"model": ErrorResponse, "description": "Service unavailable"},
    }
)
async def health_check() -> HealthResponse:
    """
    🔒 REQ-6.8: Health check endpoint.
    
    Returns HTTP 200 if:
    - Database connection is active
    - Latest data is < 48 hours old
    Otherwise returns HTTP 503.
    """
    db_connected = await check_connection()
    latest_date = await get_latest_data_date()
    
    freshness_hours = None
    if latest_date:
        try:
            latest_dt = datetime.strptime(latest_date, "%Y-%m-%d")
            latest_dt = latest_dt.replace(tzinfo=timezone.utc)
            delta = datetime.now(timezone.utc) - latest_dt
            freshness_hours = delta.total_seconds() / 3600
        except Exception:
            pass
    
    # Determine health status
    is_healthy = db_connected and (freshness_hours is None or freshness_hours < 48)
    
    if not is_healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "KOLMO_UNHEALTHY",
                    "message": "Service is not healthy",
                    "details": {
                        "database": "connected" if db_connected else "disconnected",
                        "data_freshness_hours": freshness_hours
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
        )
    
    return HealthResponse(
        status="healthy",
        version=__version__,
        database="connected" if db_connected else "disconnected",
        latest_data_date=latest_date,
        data_freshness_hours=freshness_hours
    )


def _row_to_response(row) -> WinnerResponse:
    """Convert database row to WinnerResponse."""
    import json
    
    kolmo_value = Decimal(str(row["kolmo_value"]))
    
    # Parse winner_reason JSON
    reason_data = row["winner_reason"]
    if isinstance(reason_data, str):
        reason_data = json.loads(reason_data)
    
    winner_reason = WinnerReason(
        me4u_relpath=reason_data.get("me4u_relpath"),
        iou2_relpath=reason_data.get("iou2_relpath"),
        uome_relpath=reason_data.get("uome_relpath"),
        max_relpath=reason_data.get("max_relpath"),
        tied_coins=reason_data.get("tied_coins", []),
        selection_rule=SelectionRule(reason_data.get("selection_rule", "max_positive_alphabetical_tiebreak")),
        winner=WinnerCoin(reason_data.get("winner", row["winner"]))
    )
    
    return WinnerResponse(
        date=row["date"],
        winner=WinnerCoin(row["winner"]),
        kolmo_value_str=_format_decimal_18(kolmo_value),
        kolmo_value=float(kolmo_value),
        r_me4u=_format_decimal_6(Decimal(str(row["r_me4u"]))),
        r_iou2=_format_decimal_6(Decimal(str(row["r_iou2"]))),
        r_uome=_format_decimal_6(Decimal(str(row["r_uome"]))),
        kolmo_deviation=float(row["kolmo_deviation"]),
        kolmo_state=KolmoState(row["kolmo_state"]),
        winner_reason=winner_reason,
        dist_me4u=float(row["dist_me4u"]) if row["dist_me4u"] else None,
        dist_iou2=float(row["dist_iou2"]) if row["dist_iou2"] else None,
        dist_uome=float(row["dist_uome"]) if row["dist_uome"] else None,
        relpath_me4u=float(row["relpath_me4u"]) if row["relpath_me4u"] else None,
        relpath_iou2=float(row["relpath_iou2"]) if row["relpath_iou2"] else None,
        relpath_uome=float(row["relpath_uome"]) if row["relpath_uome"] else None,
    )
