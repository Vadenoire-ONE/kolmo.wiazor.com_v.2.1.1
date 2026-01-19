"""
KOLMO Data Providers Module

🔒 REQ-3.1: Multi-provider fallback hierarchy: Frankfurter → CBR → TwelveData
"""

from kolmo.providers.base import BaseRateProvider, RateProviderError
from kolmo.providers.frankfurter import FrankfurterClient
from kolmo.providers.cbr import CBRClient
from kolmo.providers.twelvedata import TwelveDataClient
from kolmo.providers.manager import ProviderManager

__all__ = [
    "BaseRateProvider",
    "RateProviderError",
    "FrankfurterClient",
    "CBRClient",
    "TwelveDataClient",
    "ProviderManager",
]
