"""
FreeCurrencyAPI Client (Fallback Provider)

🔒 REQ-1.1: Fallback provider for exchange rates.
API Documentation: https://freecurrencyapi.com/docs/
"""

import logging
from decimal import Decimal

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from kolmo.config import get_settings
from kolmo.providers.base import BaseRateProvider, RateProviderError

logger = logging.getLogger(__name__)


class FreeCurrencyAPIClient(BaseRateProvider):
    """
    Client for FreeCurrencyAPI.
    
    FreeCurrencyAPI provides daily forex rates.
    Base currency is configurable, we use EUR.
    """
    
    PROVIDER_NAME = "freecurrencyapi"
    
    # Target currencies (we fetch EUR -> these)
    TARGET_CURRENCIES = [
        "USD", "CNY", "RUB", "INR", "AED", "CAD", "SGD", "THB", "VND", "HKD", "HUF"
    ]
    
    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.freecurrencyapi_base_url
        self.api_key = self.settings.freecurrencyapi_api_key
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def fetch_rates(self, date: str) -> dict[str, Decimal]:
        """
        Fetch rates from FreeCurrencyAPI.
        
        Args:
            date: ISO 8601 date (e.g., "2026-01-15")
        
        Returns:
            Dict with keys: eur_usd, eur_cny, eur_rub, eur_inr, eur_aed
        
        Note: FreeCurrencyAPI free tier only provides latest rates,
              not historical. For historical, use /historical endpoint.
        """
        if not self.api_key:
            raise RateProviderError(
                message="FreeCurrencyAPI key not configured",
                provider=self.PROVIDER_NAME,
                error_type="CONFIG_ERROR",
                details={"hint": "Set FREECURRENCYAPI_API_KEY environment variable"}
            )
        
        results: dict[str, Decimal | None] = {}
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Try historical endpoint first
                response = await client.get(
                    f"{self.base_url}/v1/historical",
                    params={
                        "apikey": self.api_key,
                        "base": "EUR",
                        "symbols": ",".join(self.TARGET_CURRENCIES),
                        "date": date,
                    }
                )
                
                # If historical fails (403/422 = not available on free plan), try latest
                if response.status_code in (403, 422):
                    logger.warning(
                        f"FreeCurrencyAPI historical not available, falling back to latest"
                    )
                    response = await client.get(
                        f"{self.base_url}/v1/latest",
                        params={
                            "apikey": self.api_key,
                            "base": "EUR",
                            "symbols": ",".join(self.TARGET_CURRENCIES),
                        }
                    )
                
                response.raise_for_status()
                data = response.json()
                
                # Check for API errors
                if "error" in data:
                    raise RateProviderError(
                        message=f"API error: {data.get('error', {}).get('message', 'Unknown')}",
                        provider=self.PROVIDER_NAME,
                        error_type="API_ERROR",
                        details=data.get("error", {})
                    )
                
                # Extract rates from response
                # Response format: {"data": {"USD": 1.08, "CNY": 7.85, ...}}
                rates_data = data.get("data", {})
                
                for currency in self.TARGET_CURRENCIES:
                    if currency in rates_data:
                        key = f"eur_{currency.lower()}"
                        results[key] = self._to_decimal(rates_data[currency])
            
            # Validate required rates
            if results.get("eur_usd") is None or results.get("eur_cny") is None:
                raise RateProviderError(
                    message="Missing required EUR/USD or EUR/CNY rates",
                    provider=self.PROVIDER_NAME,
                    error_type="MISSING_CURRENCY",
                    details={"available": list(results.keys())}
                )
            
            logger.info(
                f"FreeCurrencyAPI fetched rates for {date}: "
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
            )
        except httpx.RequestError as e:
            raise RateProviderError(
                message=f"Request failed: {str(e)}",
                provider=self.PROVIDER_NAME,
                error_type="REQUEST_ERROR",
                details={"error": str(e)}
            )
    
    async def health_check(self) -> bool:
        """Check if FreeCurrencyAPI is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{self.base_url}/v1/status",
                    params={"apikey": self.api_key}
                )
                return response.status_code == 200
        except Exception:
            return False
