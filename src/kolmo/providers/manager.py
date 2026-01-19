"""
Provider Manager with Fallback Hierarchy

🔒 REQ-3.1: Multi-provider fallback: Frankfurter → CBR → TwelveData
🔒 REQ-4.7: Log provider stats to mcol1_provider_stats table
"""

import logging
import time
from datetime import date as date_type
from decimal import Decimal
from typing import Literal

from kolmo.database import get_connection
from kolmo.providers.base import BaseRateProvider, RateProviderError
from kolmo.providers.frankfurter import FrankfurterClient
from kolmo.providers.cbr import CBRClient
from kolmo.providers.twelvedata import TwelveDataClient

logger = logging.getLogger(__name__)

ProviderName = Literal["frankfurter", "cbr", "twelvedata"]


class ProviderManager:
    """
    Manages multi-provider fallback hierarchy.
    
    🔒 REQ-1.1: Fetch daily rates from at least three providers
    with automatic hierarchical fallback.
    """
    
    def __init__(self):
        self.providers: list[tuple[ProviderName, BaseRateProvider]] = [
            ("frankfurter", FrankfurterClient()),
            ("cbr", CBRClient()),
            ("twelvedata", TwelveDataClient()),
        ]
    
    async def fetch_with_fallback(
        self,
        date: str
    ) -> tuple[dict[str, Decimal], ProviderName]:
        """
        Attempt providers in order: Frankfurter → CBR → TwelveData.
        
        Args:
            date: ISO 8601 date string (e.g., "2026-01-15")
        
        Returns:
            Tuple of (rates_dict, provider_name_used)
        
        Raises:
            RuntimeError: If all providers fail
        """
        errors: list[RateProviderError] = []
        
        for idx, (name, client) in enumerate(self.providers, start=1):
            start_time = time.time()
            
            try:
                logger.info(f"Attempting {name} (attempt {idx}/{len(self.providers)})")
                
                rates = await client.fetch_rates(date)
                
                latency_ms = int((time.time() - start_time) * 1000)
                await self._log_stats(
                    date=date,
                    provider=name,
                    attempt_order=idx,
                    success=True,
                    latency_ms=latency_ms,
                    error_type=None,
                    error_message=None
                )
                
                logger.info(f"✅ {name} success ({latency_ms}ms)")
                return rates, name
                
            except RateProviderError as e:
                latency_ms = int((time.time() - start_time) * 1000)
                errors.append(e)
                
                await self._log_stats(
                    date=date,
                    provider=name,
                    attempt_order=idx,
                    success=False,
                    latency_ms=latency_ms,
                    error_type=e.error_type,
                    error_message=str(e)
                )
                
                logger.warning(f"❌ {name} failed: {e}")
                
                if idx == len(self.providers):
                    # Last provider failed - raise aggregated error
                    raise RuntimeError(
                        f"All providers failed. Errors: "
                        f"{[(e.provider, e.error_type) for e in errors]}"
                    ) from e
                
                # Try next provider
                continue
            
            except Exception as e:
                latency_ms = int((time.time() - start_time) * 1000)
                
                await self._log_stats(
                    date=date,
                    provider=name,
                    attempt_order=idx,
                    success=False,
                    latency_ms=latency_ms,
                    error_type="UNKNOWN",
                    error_message=str(e)
                )
                
                logger.error(f"❌ {name} unexpected error: {e}")
                
                if idx == len(self.providers):
                    raise RuntimeError(f"All providers failed. Last error: {e}") from e
                
                continue
        
        # Should not reach here
        raise RuntimeError("No providers available")
    
    async def _log_stats(
        self,
        date: str,
        provider: ProviderName,
        attempt_order: int,
        success: bool,
        latency_ms: int,
        error_type: str | None,
        error_message: str | None
    ) -> None:
        """
        🔒 REQ-4.7: Log provider stats to mcol1_provider_stats table.
        """
        try:
            async with get_connection() as conn:
                await conn.execute(
                    """
                    INSERT INTO mcol1_provider_stats (
                        date, provider_name, attempt_order, success, 
                        latency_ms, error_type, error_message
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    date_type.fromisoformat(date),
                    provider,
                    attempt_order,
                    success,
                    latency_ms,
                    error_type,
                    error_message[:500] if error_message else None
                )
        except Exception as e:
            # Don't fail the main operation if stats logging fails
            logger.error(f"Failed to log provider stats: {e}")
    
    async def health_check_all(self) -> dict[ProviderName, bool]:
        """Check health status of all providers."""
        results: dict[ProviderName, bool] = {}
        
        for name, client in self.providers:
            results[name] = await client.health_check()
        
        return results
