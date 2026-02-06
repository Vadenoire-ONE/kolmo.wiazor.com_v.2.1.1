"""
Central Bank of Russia (CBR) API Client (Fallback 1)

🔒 REQ-1.1: First fallback provider for exchange rates.
API Documentation: https://www.cbr.ru/development/SXML/
"""

import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from decimal import Decimal

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from kolmo.config import get_settings
from kolmo.providers.base import BaseRateProvider, RateProviderError

logger = logging.getLogger(__name__)


class CBRClient(BaseRateProvider):
    """
    Client for Central Bank of Russia XML exchange rates.
    
    CBR provides rates against RUB. We need to cross-calculate EUR-based rates.
    Response format: XML with ValCurs/Valute elements
    """
    
    PROVIDER_NAME = "cbr"
    
    # CBR currency codes
    CURRENCY_CODES = {
        "USD": "R01235",
        "EUR": "R01239",
        "CNY": "R01375",
        "INR": "R01270",
        "AED": "R01230",
        "CAD": "R01350",
        "SGD": "R01395",
        "THB": "R01675",
        "VND": "R01700",
        "HKD": "R01200",
        "HUF": "R01565",
    }
    
    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.cbr_base_url
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def fetch_rates(self, date: str) -> dict[str, Decimal]:
        """
        Fetch rates from CBR and convert to EUR-based.
        
        Args:
            date: ISO 8601 date (e.g., "2026-01-15")
        
        Returns:
            Dict with keys: eur_usd, eur_cny, eur_rub, eur_inr, eur_aed
        """
        # Convert date format for CBR (DD/MM/YYYY)
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        cbr_date = date_obj.strftime("%d/%m/%Y")
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    self.base_url,
                    params={"date_req": cbr_date}
                )
                response.raise_for_status()
            
            # Parse XML response
            root = ET.fromstring(response.content)
            
            # Extract rates (all rates are against RUB)
            rates_rub: dict[str, Decimal] = {}
            
            for valute in root.findall("Valute"):
                char_code = valute.find("CharCode")
                value = valute.find("Value")
                nominal = valute.find("Nominal")
                if char_code is not None and value is not None and nominal is not None:
                    code = char_code.text
                    if code in self.CURRENCY_CODES:
                        # CBR uses comma as decimal separator
                        rate_value = Decimal(value.text.replace(",", "."))
                        nominal_value = Decimal(nominal.text)
                        # Rate per 1 unit
                        rates_rub[code] = rate_value / nominal_value
            
            # Validate required currencies
            if "EUR" not in rates_rub or "USD" not in rates_rub:
                raise RateProviderError(
                    message="Missing EUR or USD in CBR response",
                    provider=self.PROVIDER_NAME,
                    error_type="MISSING_CURRENCY",
                    details={"available": list(rates_rub.keys())}
                )
            
            # Cross-calculate EUR-based rates
            # EUR/USD = (RUB/USD) / (RUB/EUR) = EUR_rate_rub / USD_rate_rub
            eur_rate_rub = rates_rub["EUR"]
            
            result = {
                "eur_usd": eur_rate_rub / rates_rub["USD"] if "USD" in rates_rub else None,
                "eur_cny": eur_rate_rub / rates_rub["CNY"] if "CNY" in rates_rub else None,
                "eur_rub": eur_rate_rub,  # EUR/RUB direct
                "eur_inr": eur_rate_rub / rates_rub["INR"] if "INR" in rates_rub else None,
                "eur_aed": eur_rate_rub / rates_rub["AED"] if "AED" in rates_rub else None,
                "eur_cad": eur_rate_rub / rates_rub["CAD"] if "CAD" in rates_rub else None,
                "eur_sgd": eur_rate_rub / rates_rub["SGD"] if "SGD" in rates_rub else None,
                "eur_thb": eur_rate_rub / rates_rub["THB"] if "THB" in rates_rub else None,
                "eur_vnd": eur_rate_rub / rates_rub["VND"] if "VND" in rates_rub else None,
                "eur_hkd": eur_rate_rub / rates_rub["HKD"] if "HKD" in rates_rub else None,
                "eur_huf": eur_rate_rub / rates_rub["HUF"] if "HUF" in rates_rub else None,
            }
            
            logger.info(
                f"CBR fetched rates for {date}: "
                f"EUR/USD={result['eur_usd']}, EUR/CNY={result.get('eur_cny')}"
            )
            
            return result
            
        except ET.ParseError as e:
            raise RateProviderError(
                message=f"XML parse error: {e}",
                provider=self.PROVIDER_NAME,
                error_type="PARSE_ERROR",
                details={}
            ) from e
            
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
        """Check if CBR API is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(self.base_url)
                return response.status_code == 200
        except Exception:
            return False
