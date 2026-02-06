"""
Frankfurter API Client (Primary Provider)

🔒 REQ-1.1: Primary provider for EUR-based exchange rates.
API Documentation: https://www.frankfurter.app/docs/
"""

import logging
from datetime import date as date_type
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
    REQUIRED_CURRENCIES = {
        "USD", "CNY", "RUB", "INR", "AED", "CAD", "SGD", "THB", "VND", "HKD", "HUF"
    }
    
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
            Dict with keys: rub_usd, rub_cny, rub_eur, rub_inr, rub_aed
        
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
                    f"{self.base_url}/v1/{date}",
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
            # Extract EUR-based quotes first (local names without 'eur_' prefix)
            rate_usd = self._to_decimal(data["rates"].get("USD"))
            rate_cny = self._to_decimal(data["rates"].get("CNY"))
            rate_rub = self._to_decimal(data["rates"].get("RUB"))
            rate_inr = self._to_decimal(data["rates"].get("INR"))
            rate_aed = self._to_decimal(data["rates"].get("AED"))

            # Convert to RUB-based fields when possible:
            # rub_usd = EUR/RUB / EUR/USD = RUB per USD
            rub_usd = (rate_rub / rate_usd) if (rate_rub is not None and rate_usd is not None) else None
            # rub_cny = EUR/RUB / EUR/CNY = RUB per CNY
            rub_cny = (rate_rub / rate_cny) if (rate_rub is not None and rate_cny is not None) else None

            rates = {
                "rub_usd": rub_usd,
                "rub_cny": rub_cny,
                "rub_eur": rate_rub,
                "rub_inr": (rate_rub / rate_inr) if (rate_rub is not None and rate_inr is not None) else None,
                "rub_aed": (rate_rub / rate_aed) if (rate_rub is not None and rate_aed is not None) else None,
                "cad": self._to_decimal(data["rates"].get("CAD")),
                "sgd": self._to_decimal(data["rates"].get("SGD")),
                "thb": self._to_decimal(data["rates"].get("THB")),
                "vnd": None,
                "hkd": self._to_decimal(data["rates"].get("HKD")),
                "huf": self._to_decimal(data["rates"].get("HUF")),
            }
            
            # Validate required rates present
            if rates["rub_usd"] is None or rates["rub_cny"] is None:
                raise RateProviderError(
                    message="Missing required currencies to derive RUB-based USD/CNY",
                    provider=self.PROVIDER_NAME,
                    error_type="MISSING_CURRENCY",
                    details={"available": list(received)}
                )

            logger.info(
                f"Frankfurter fetched rates for {date}: RUB/USD={rates['rub_usd']}, RUB/CNY={rates['rub_cny']}"
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

    async def fetch_rates_bulk(
        self, 
        start_date: str, 
        end_date: str
    ) -> dict[str, dict[str, Decimal]]:
        """
        Fetch EUR-based rates from Frankfurter API for a date range.
        
        Uses the bulk endpoint: /v1/{start_date}..{end_date}
        
        Note: Frankfurter doesn't provide RUB, AED, VND - those will be None.
        
        Args:
            start_date: ISO 8601 date (e.g., "2021-07-01")
            end_date: ISO 8601 date (e.g., "2026-01-29")
        
            Returns:
            Dict mapping date strings to rate dicts (keys use plain currency codes):
            {
                "2021-07-01": {"usd": Decimal("1.18"), ...},
                "2021-07-02": {"usd": Decimal("1.19"), ...},
            }
        
        Raises:
            RateProviderError: If API returns error
        """
        # Request only currencies that Frankfurter actually provides
        # RUB, AED, VND are NOT available from Frankfurter/ECB
        available_currencies = {"USD", "CNY", "INR", "CAD", "SGD", "THB", "HKD", "HUF"}
        
        params = {
            "base": "EUR",
            "symbols": ",".join(available_currencies)
        }
        
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # Use extended timeout for bulk requests
                async with httpx.AsyncClient(timeout=120.0) as client:
                    url = f"{self.base_url}/v1/{start_date}..{end_date}"
                    logger.info(f"Frankfurter bulk request: {start_date} to {end_date} (attempt {attempt + 1}/{max_retries})")
                    
                    response = await client.get(url, params=params)
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
                
                # data["rates"] is a dict: {"2021-07-01": {"USD": 1.18, ...}, ...}
                results = {}
                
                for date_str, day_rates in data["rates"].items():
                    # Convert to our format with Decimal values
                    # Note: RUB, AED, VND will be None - they're not available from Frankfurter
                    # For bulk responses, RUB not available from Frankfurter
                    results[date_str] = {
                        "rub_usd": None,
                        "rub_cny": None,
                        "rub_eur": None,
                        "rub_inr": None,
                        "rub_aed": None,
                        "cad": self._to_decimal(day_rates.get("CAD")),
                        "sgd": self._to_decimal(day_rates.get("SGD")),
                        "thb": self._to_decimal(day_rates.get("THB")),
                        "vnd": None,
                        "hkd": self._to_decimal(day_rates.get("HKD")),
                        "huf": self._to_decimal(day_rates.get("HUF")),
                    }
                
                logger.info(
                    f"Frankfurter bulk fetched {len(results)} dates: "
                    f"{start_date} to {end_date}"
                )
                
                return results
                
            except httpx.HTTPStatusError as e:
                last_error = RateProviderError(
                    message=f"HTTP error: {e.response.status_code}",
                    provider=self.PROVIDER_NAME,
                    error_type=f"HTTP_{e.response.status_code}",
                    details={"url": str(e.request.url)}
                )
                logger.warning(f"Frankfurter bulk HTTP error (attempt {attempt + 1}): {e.response.status_code}")
                
            except httpx.TimeoutException as e:
                last_error = RateProviderError(
                    message="Request timeout",
                    provider=self.PROVIDER_NAME,
                    error_type="TIMEOUT",
                    details={"timeout_seconds": 120}
                )
                logger.warning(f"Frankfurter bulk timeout (attempt {attempt + 1})")
                
            except Exception as e:
                if isinstance(e, RateProviderError):
                    last_error = e
                else:
                    last_error = RateProviderError(
                        message=str(e),
                        provider=self.PROVIDER_NAME,
                        error_type="UNKNOWN",
                        details={}
                    )
                logger.warning(f"Frankfurter bulk error (attempt {attempt + 1}): {e}")
            
            # Wait before retry
            if attempt < max_retries - 1:
                import asyncio
                await asyncio.sleep(2 ** attempt)
        
        # All retries failed
        raise last_error

