"""
KOLMO Data Models

🔒 NORMATIVE SECTION - All models follow Technical Specification v.2.1.1

REQ-2.1: All KOLMO rates MUST be stored and computed using Python decimal.Decimal type.
REQ-4.1: All database identifiers MUST use snake_case.
REQ-4.5: winner_reason JSONB column MUST contain explainability metadata.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


# === Enums ===

class KolmoState(str, Enum):
    """KOLMO invariant state based on deviation from 1.0."""
    OK = "OK"          # deviation < 1%
    WARN = "WARN"      # 1% ≤ deviation < 5%
    CRITICAL = "CRITICAL"  # deviation ≥ 5%


class WinnerCoin(str, Enum):
    """
    KOLMO coin identifiers.
    
    🔒 REQ-2.6: Tie-break alphabetical order: IOU2 < ME4U < UOME
    """
    IOU2 = "IOU2"  # EUR/USD
    ME4U = "ME4U"  # USD/CNY
    UOME = "UOME"  # CNY/EUR


class SelectionRule(str, Enum):
    """Winner selection rule for explainability."""
    MAX_POSITIVE_ALPHABETICAL_TIEBREAK = "max_positive_alphabetical_tiebreak"
    LEAST_NEGATIVE = "least_negative"
    DEFAULT_FIRST_DAY = "default_first_day"


class ProviderName(str, Enum):
    """External data provider names."""
    FRANKFURTER = "frankfurter"
    CBR = "cbr"
    TWELVEDATA = "twelvedata"


class CurrencyPair(str, Enum):
    """Currency pair descriptors."""
    RUB_USD = "RUB/USD"
    USD_RUB = "USD/RUB"
    RUB_CNY = "RUB/CNY"
    CNY_RUB = "CNY/RUB"
    RUB_EUR = "RUB/EUR"
    EUR_RUB = "EUR/RUB"
    RUB_INR = "RUB/INR"
    INR_RUB = "INR/RUB"
    RUB_AED = "RUB/AED"
    AED_RUB = "AED/RUB"


# === Winner Reason (Explainability) ===

class WinnerReason(BaseModel):
    """
    🔒 REQ-4.5 & REQ-5.9: Explainability metadata for winner selection.
    
    This JSONB structure explains WHY each coin won for regulatory transparency.
    """
    me4u_relpath: float | None = Field(
        description="ME4U RelativePath value (None if first day)"
    )
    iou2_relpath: float | None = Field(
        description="IOU2 RelativePath value (None if first day)"
    )
    uome_relpath: float | None = Field(
        description="UOME RelativePath value (None if first day)"
    )
    max_relpath: float | None = Field(
        default=None,
        description="Maximum RelativePath among candidates"
    )
    tied_coins: list[str] = Field(
        default_factory=list,
        description="List of coins that tied for max (if any)"
    )
    selection_rule: SelectionRule = Field(
        description="Rule applied to select winner"
    )
    winner: WinnerCoin = Field(
        description="Selected winning coin"
    )


# === External Data (Raw Provider Data) ===

class ExternalDataCreate(BaseModel):
    """
    🔒 REQ-4.2: mcol1_external_data - Immutable raw exchange rates from providers.
    
    This model represents data as received from external APIs before any transformation.
    """
    date: date
    
    # RUB-based rates from providers
    rub_usd: Decimal = Field(ge=Decimal("0.0001"), le=Decimal("100000"))
    rub_usd_pair_desc: CurrencyPair = CurrencyPair.RUB_USD

    rub_cny: Decimal = Field(ge=Decimal("0.0001"), le=Decimal("100000"))
    rub_cny_pair_desc: CurrencyPair = CurrencyPair.RUB_CNY

    rub_eur: Decimal | None = Field(default=None, ge=Decimal("0.0001"), le=Decimal("100000"))
    rub_eur_pair_desc: CurrencyPair | None = CurrencyPair.RUB_EUR

    rub_inr: Decimal | None = Field(default=None, ge=Decimal("0.0001"), le=Decimal("100000"))
    rub_inr_pair_desc: CurrencyPair | None = CurrencyPair.RUB_INR

    rub_aed: Decimal | None = Field(default=None, ge=Decimal("0.0001"), le=Decimal("100000"))
    rub_aed_pair_desc: CurrencyPair | None = CurrencyPair.RUB_AED
    
    # Audit trail
    mcol1_snapshot_id: UUID = Field(default_factory=uuid4)
    trace_id: UUID = Field(default_factory=uuid4)
    sources: dict[str, Any] = Field(default_factory=dict)
    
    @field_validator("rub_usd", "rub_cny", "rub_eur", "rub_inr", "rub_aed", mode="before")
    @classmethod
    def convert_to_decimal(cls, v: Any) -> Decimal | None:
        """🔒 REQ-2.1: Ensure all rates are Decimal type."""
        if v is None:
            return None
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))


class ExternalData(ExternalDataCreate):
    """External data with database-generated fields."""
    id: UUID
    created_at: datetime
    updated_at: datetime


# === Compute Data (Derived KOLMO Metrics) ===

class KolmoRates(BaseModel):
    """
    🔒 REQ-2.1 KOLMO Rates (Standard Notation)
    
    These define the three "coins" used in DTKT clearing.
    
    r_me4u: ME4U coin = USD/CNY (US Dollars per 1 Chinese Yuan)
            Example: Decimal('0.1434') means "1 yuan = 0.1434 dollars"
            Or equivalently: "1 dollar buys 6.9748 yuan"
    
        r_iou2: IOU2 coin = RUB/USD (Rubles per 1 US Dollar)
            Example: Decimal('76.55') means "1 dollar = 76.55 rubles"
            Or equivalently: "1 ruble buys 0.013063 dollars"

        r_uome: UOME coin = CNY/RUB (Chinese Yuan per 1 Ruble)
            Example: Decimal('0.090966') means "1 ruble = 0.090966 yuan"
            Or equivalently: "1 yuan buys 10.99 rubles"
    """
    r_me4u: Decimal = Field(
        gt=Decimal("0"),
        description="ME4U coin = USD/CNY (US Dollars per 1 Chinese Yuan). Example: 0.1434 means 1 yuan = 0.1434 dollars"
    )
    r_iou2: Decimal = Field(
        gt=Decimal("0"),
        description="IOU2 coin = EUR/USD (Euros per 1 US Dollar). Example: 0.8599 means 1 dollar = 0.8599 euros"
    )
    r_uome: Decimal = Field(
        gt=Decimal("0"),
        description="UOME coin = CNY/EUR (Chinese Yuan per 1 Euro). Example: 8.11 means 1 euro = 8.11 yuan"
    )
    
    @field_validator("r_me4u", "r_iou2", "r_uome", mode="before")
    @classmethod
    def convert_to_decimal(cls, v: Any) -> Decimal:
        """🔒 REQ-2.1: Ensure all rates are Decimal type."""
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))


class ComputeDataCreate(BaseModel):
    """
    🔒 REQ-4.3: mcol1_compute_data - Derived KOLMO metrics.
    
    Every row MUST link to exactly one external snapshot via mcol1_snapshot_id FK.
    """
    date: date
    
    # KOLMO rates (standardized notation)
    r_me4u: Decimal = Field(gt=Decimal("0"))
    r_iou2: Decimal = Field(gt=Decimal("0"))
    r_uome: Decimal = Field(gt=Decimal("0"))
    
    # 🔒 Amendment A1: EXACT decimal KOLMO invariant
    kolmo_value: Decimal = Field(
        description="🔒 CRITICAL: Exact product r_me4u * r_iou2 * r_uome (NUMERIC(28,18))"
    )
    kolmo_deviation: Decimal = Field(
        ge=Decimal("0"),
        description="Absolute deviation from 1.0 as percentage"
    )
    kolmo_state: KolmoState
    
    # Distance metrics
    dist_me4u: Decimal
    dist_iou2: Decimal
    dist_uome: Decimal
    
    # RelativePath metrics (None for first day)
    relpath_me4u: Decimal | None = None
    relpath_iou2: Decimal | None = None
    relpath_uome: Decimal | None = None
    
    # Volatility metrics (daily volatility index)
    vol_me4u: Decimal | None = Field(default=None, description="Daily volatility index of ME4U")
    vol_iou2: Decimal | None = Field(default=None, description="Daily volatility index of IOU2")
    vol_uome: Decimal | None = Field(default=None, description="Daily volatility index of UOME")
    
    # Winner selection
    winner: WinnerCoin
    winner_reason: WinnerReason
    
    # Audit trail
    mcol1_snapshot_id: UUID = Field(
        description="FK to mcol1_external_data.mcol1_snapshot_id"
    )
    mcol1_snapshot_compute_id: UUID = Field(default_factory=uuid4)
    trace_compute_id: UUID = Field(default_factory=uuid4)
    
    @model_validator(mode="after")
    def validate_kolmo_exact_product(self) -> "ComputeDataCreate":
        """
        🔒 REQ-4.4 & REQ-5.2: Validate kolmo_value is exact product.
        
        Amendment A1: The system MUST validate dimensional analysis.
        """
        computed = self.r_me4u * self.r_iou2 * self.r_uome
        if self.kolmo_value != computed:
            raise ValueError(
                f"🔒 Amendment A1 Violation: kolmo_value ({self.kolmo_value}) "
                f"!= r_me4u * r_iou2 * r_uome ({computed})"
            )
        return self
    
    @field_validator(
        "r_me4u", "r_iou2", "r_uome", "kolmo_value", "kolmo_deviation",
        "dist_me4u", "dist_iou2", "dist_uome",
        "relpath_me4u", "relpath_iou2", "relpath_uome",
        "vol_me4u", "vol_iou2", "vol_uome",
        mode="before"
    )
    @classmethod
    def convert_to_decimal(cls, v: Any) -> Decimal | None:
        """🔒 REQ-2.1: Ensure all numeric values are Decimal type."""
        if v is None:
            return None
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))


class ComputeData(ComputeDataCreate):
    """Compute data with database-generated fields."""
    id: UUID
    created_at: datetime
    updated_at: datetime


# === Provider Stats (Operational Telemetry) ===

class ProviderStatsCreate(BaseModel):
    """
    🔒 REQ-4.7: mcol1_provider_stats - Provider reliability tracking.
    """
    date: date
    provider_name: ProviderName
    attempt_order: int = Field(ge=1, le=3)
    success: bool
    latency_ms: int | None = Field(default=None, ge=0)
    error_type: str | None = None
    error_message: str | None = None


class ProviderStats(ProviderStatsCreate):
    """Provider stats with database-generated fields."""
    id: UUID
    created_at: datetime
