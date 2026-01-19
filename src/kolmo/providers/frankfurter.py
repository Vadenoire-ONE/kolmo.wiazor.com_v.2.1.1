"""
Frankfurter API Client (Primary Provider)

🔒 REQ-1.1: Primary provider for EUR-based exchange rates.
API Documentation: https://www.frankfurter.app/docs/
"""

import logging
from decimal import Decimal

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from kolmo.config import get_settings
from kolmo.providers.base import BaseRateProvider, RateProviderError

logger = logging.getLogger(__name__)


class FrankfurterClient(BaseRateProvider):
    """
    Client for Frankfurter.dev EUR-based exchange rates.
    
    Frankfurter provides free FX rates from ECB (European Central Bank).
    Response format: {"date": "2026-01-15", "base": "EUR", "rates": {"USD": 1.163, "CNY": 8.11}}
    """
    
    PROVIDER_NAME = "frankfurter"
    REQUIRED_CURRENCIES = {"USD", "CNY", "RUB", "INR", "AED"}
    
    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.frankfurter_base_url
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def fetch_rates(self, date: str) -> dict[str, Decimal]:
        """
        Fetch EUR-based rates from Frankfurter API.
        
        Args:
            date: ISO 8601 date (e.g., "2026-01-15")
        
        Returns:
            Dict with keys: eur_usd, eur_cny, eur_rub, eur_inr, eur_aed
        
        Raises:
            RateProviderError: If API returns error or missing currencies
        """
        params = {
            "base": "EUR",
            "symbols": ",".join(self.REQUIRED_CURRENCIES)
        }
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/{date}",
                    params=params
                )
                response.raise_for_status()
                data = response.json()
            
            # Validate response structure
            if "rates" not in data:
                raise RateProviderError(
                    message="Invalid response: missing 'rates' field",
                    provider=self.PROVIDER_NAME,
                    error_type="PARSE_ERROR",
                    details={"response": data}
                )
            
            # Check for missing currencies
            received = set(data["rates"].keys())
            missing = self.REQUIRED_CURRENCIES - received
            if missing:
                logger.warning(
                    f"Frankfurter missing currencies: {missing}. "
                    f"Available: {received}"
                )
                # Don't fail - some currencies may not be available on weekends
            
            # 🔒 REQ-2.1: Convert to exact Decimal
            rates = {
                "eur_usd": self._to_decimal(data["rates"].get("USD")),
                "eur_cny": self._to_decimal(data["rates"].get("CNY")),
                "eur_rub": self._to_decimal(data["rates"].get("RUB")) if "RUB" in data["rates"] else None,
                "eur_inr": self._to_decimal(data["rates"].get("INR")) if "INR" in data["rates"] else None,
                "eur_aed": self._to_decimal(data["rates"].get("AED")) if "AED" in data["rates"] else None,
            }
            
            # Validate required rates present
            if rates["eur_usd"] is None or rates["eur_cny"] is None:
                raise RateProviderError(
                    message="Missing required currencies: USD or CNY",
                    provider=self.PROVIDER_NAME,
                    error_type="MISSING_CURRENCY",
                    details={"available": list(received)}
                )
            
            logger.info(
                f"Frankfurter fetched rates for {date}: "
                f"EUR/USD={rates['eur_usd']}, EUR/CNY={rates['eur_cny']}"
            )
            
            return rates
            
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
                details={"timeout_seconds": 10}
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
        """Check if Frankfurter API is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/latest")
                return response.status_code == 200
        except Exception:
            return False
