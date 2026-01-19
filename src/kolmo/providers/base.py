"""
Base Rate Provider Interface

🔒 REQ-2.1: All rates MUST be returned as decimal.Decimal type.
"""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any


class RateProviderError(Exception):
    """Base exception for rate provider errors."""
    
    def __init__(
        self,
        message: str,
        provider: str,
        error_type: str = "UNKNOWN",
        details: dict[str, Any] | None = None
    ):
        super().__init__(message)
        self.provider = provider
        self.error_type = error_type
        self.details = details or {}


class BaseRateProvider(ABC):
    """
    Abstract base class for exchange rate providers.
    
    All implementations MUST return rates as Decimal type.
    """
    
    PROVIDER_NAME: str = "base"
    
    @abstractmethod
    async def fetch_rates(self, date: str) -> dict[str, Decimal]:
        """
        Fetch EUR-based exchange rates for a specific date.
        
        Args:
            date: ISO 8601 date string (e.g., "2026-01-15")
        
        Returns:
            Dict with keys: eur_usd, eur_cny, eur_rub, eur_inr, eur_aed
            All values MUST be Decimal type.
        
        Raises:
            RateProviderError: If fetching fails
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if provider is reachable and responding."""
        pass
    
    def _to_decimal(self, value: Any) -> Decimal:
        """
        🔒 REQ-2.1: Convert value to exact Decimal.
        
        NEVER use float conversion - always use str intermediate.
        """
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))
