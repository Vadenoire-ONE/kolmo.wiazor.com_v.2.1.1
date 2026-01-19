"""
TwelveData API Client (Fallback 2)

🔒 REQ-1.1: Second fallback provider for exchange rates.
API Documentation: https://twelvedata.com/docs
"""

import logging
from decimal import Decimal

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from kolmo.config import get_settings
from kolmo.providers.base import BaseRateProvider, RateProviderError

logger = logging.getLogger(__name__)


class TwelveDataClient(BaseRateProvider):
    """
    Client for TwelveData forex API.
    
    TwelveData provides real-time and historical forex data.
    Requires API key for access.
    """
    
    PROVIDER_NAME = "twelvedata"
    
    # Currency pairs to fetch
    PAIRS = ["EUR/USD", "EUR/CNY", "EUR/RUB", "EUR/INR", "EUR/AED"]
    
    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.twelvedata_base_url
        self.api_key = self.settings.twelvedata_api_key
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def fetch_rates(self, date: str) -> dict[str, Decimal]:
        """
        Fetch rates from TwelveData API.
        
        Args:
            date: ISO 8601 date (e.g., "2026-01-15")
        
        Returns:
            Dict with keys: eur_usd, eur_cny, eur_rub, eur_inr, eur_aed
        """
        if not self.api_key:
            raise RateProviderError(
                message="TwelveData API key not configured",
                provider=self.PROVIDER_NAME,
                error_type="CONFIG_ERROR",
                details={"hint": "Set TWELVEDATA_API_KEY environment variable"}
            )
        
        results: dict[str, Decimal | None] = {}
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                for pair in self.PAIRS:
                    # TwelveData time_series endpoint for historical data
                    response = await client.get(
                        f"{self.base_url}/time_series",
                        params={
                            "symbol": pair,
                            "interval": "1day",
                            "start_date": date,
                            "end_date": date,
                            "apikey": self.api_key,
                        }
                    )
                    response.raise_for_status()
                    data = response.json()
                    
                    # Check for API errors
                    if "code" in data and data["code"] != 200:
                        logger.warning(
                            f"TwelveData error for {pair}: {data.get('message', 'Unknown')}"
                        )
                        continue
                    
                    # Extract close price
                    if "values" in data and len(data["values"]) > 0:
                        close_price = data["values"][0].get("close")
                        if close_price:
                            key = f"eur_{pair.split('/')[1].lower()}"
                            results[key] = self._to_decimal(close_price)
            
            # Validate required rates
            if results.get("eur_usd") is None or results.get("eur_cny") is None:
                raise RateProviderError(
                    message="Missing required EUR/USD or EUR/CNY rates",
                    provider=self.PROVIDER_NAME,
                    error_type="MISSING_CURRENCY",
                    details={"available": list(results.keys())}
                )
            
            logger.info(
                f"TwelveData fetched rates for {date}: "
                f"EUR/USD={results.get('eur_usd')}, EUR/CNY={results.get('eur_cny')}"
            )
            
            return {
                "eur_usd": results.get("eur_usd"),
                "eur_cny": results.get("eur_cny"),
                "eur_rub": results.get("eur_rub"),
                "eur_inr": results.get("eur_inr"),
                "eur_aed": results.get("eur_aed"),
            }
            
        except httpx.HTTPStatusError as e:
            raise RateProviderError(
                message=f"HTTP error: {e.response.status_code}",
                provider=self.PROVIDER_NAME,
                error_type=f"HTTP_{e.response.status_code}",
                details={"url": str(e.request.url)}
            ) from e
            
        except httpx.TimeoutException as e:
            raise RateProviderError(
                message="Request timeout",
                provider=self.PROVIDER_NAME,
                error_type="TIMEOUT",
                details={"timeout_seconds": 15}
            ) from e
            
        except Exception as e:
            if isinstance(e, RateProviderError):
                raise
            raise RateProviderError(
                message=str(e),
                provider=self.PROVIDER_NAME,
                error_type="UNKNOWN",
                details={}
            ) from e
    
    async def health_check(self) -> bool:
        """Check if TwelveData API is reachable."""
        if not self.api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{self.base_url}/api_usage",
                    params={"apikey": self.api_key}
                )
                return response.status_code == 200
        except Exception:
            return False
