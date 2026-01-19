"""
KOLMO Calculator - Compute KOLMO invariant and metrics

🔒 REQ-2.2: KOLMO invariant MUST be computed as exact product with no rounding.
🔒 REQ-4.4: kolmo_value MUST be stored as NUMERIC(28,18) exact product.
🔒 REQ-5.3: Decimal precision context MUST be at least 28 digits.
"""

from decimal import Decimal, getcontext

from kolmo.models import KolmoRates, KolmoState

# 🔒 REQ-5.3: Set decimal precision
getcontext().prec = 28


class KOLMOCalculator:
    """
    Calculate KOLMO invariant and related metrics.
    
    KOLMO Invariant: K = r_me4u × r_iou2 × r_uome
    
    Interpretation:
    - K = 1.0: Perfect arbitrage-free market
    - 0.995 ≤ K ≤ 1.005: Normal market conditions (±0.5%)
    - K < 0.995 or K > 1.005: Significant market inefficiency
    """
    
    # State thresholds
    WARN_THRESHOLD = Decimal("0.01")  # 1%
    CRITICAL_THRESHOLD = Decimal("0.05")  # 5%
    
    def compute_kolmo_value(
        self,
        r_me4u: Decimal,
        r_iou2: Decimal,
        r_uome: Decimal
    ) -> Decimal:
        """
        🔒 REQ-2.2: Compute EXACT KOLMO invariant.
        
        Args:
            r_me4u: ME4U rate (USD/CNY)
            r_iou2: IOU2 rate (EUR/USD)
            r_uome: UOME rate (CNY/EUR)
        
        Returns:
            Exact product as Decimal with no rounding.
        """
        # 🔒 Amendment A1: EXACT multiplication, no rounding
        return r_me4u * r_iou2 * r_uome
    
    def compute_deviation(self, kolmo_value: Decimal) -> Decimal:
        """
        Compute absolute deviation from perfect invariant (1.0).
        
        Args:
            kolmo_value: KOLMO invariant value
        
        Returns:
            Deviation as decimal (e.g., 0.0041 for 0.41%)
        """
        return abs(kolmo_value - Decimal("1.0"))
    
    def compute_state(self, kolmo_value: Decimal) -> KolmoState:
        """
        Determine KOLMO state based on deviation.
        
        States:
        - OK: deviation < 1%
        - WARN: 1% ≤ deviation < 5%
        - CRITICAL: deviation ≥ 5%
        """
        deviation = self.compute_deviation(kolmo_value)
        
        if deviation < self.WARN_THRESHOLD:
            return KolmoState.OK
        elif deviation < self.CRITICAL_THRESHOLD:
            return KolmoState.WARN
        else:
            return KolmoState.CRITICAL
    
    def compute_distance(self, rate: Decimal) -> Decimal:
        """
        🔒 REQ-2.3: Compute distance from parity (rate = 1.0).
        
        Definition: dist = |rate - 1.0| × 100
        
        Args:
            rate: KOLMO rate value
        
        Returns:
            Distance as percentage (e.g., 85.66 for 85.66%)
        """
        return abs(rate - Decimal("1.0")) * Decimal("100")
    
    def compute_distances(
        self,
        rates: KolmoRates
    ) -> tuple[Decimal, Decimal, Decimal]:
        """
        Compute distances for all three KOLMO rates.
        
        Returns:
            Tuple of (dist_me4u, dist_iou2, dist_uome)
        """
        return (
            self.compute_distance(rates.r_me4u),
            self.compute_distance(rates.r_iou2),
            self.compute_distance(rates.r_uome)
        )
    
    def compute_relativepath(
        self,
        dist_current: Decimal,
        dist_previous: Decimal | None
    ) -> Decimal | None:
        """
        🔒 REQ-2.4: Compute RelativePath (improvement toward parity).
        
        Definition: relpath = (dist_prev - dist_curr) / dist_prev × 100
        
        Args:
            dist_current: Today's distance
            dist_previous: Yesterday's distance (None if first day)
        
        Returns:
            RelativePath as percentage, or None if no previous data
        
        Interpretation:
        - relpath > 0: Rate is improving (moving toward parity)
        - relpath < 0: Rate is deteriorating (moving away from parity)
        """
        # 🔒 REQ-5.5: NULL for first day or division by zero
        if dist_previous is None or dist_previous == Decimal("0"):
            return None
        
        return ((dist_previous - dist_current) / dist_previous) * Decimal("100")
    
    def compute_all_relativepaths(
        self,
        dist_me4u: Decimal,
        dist_iou2: Decimal,
        dist_uome: Decimal,
        prev_dist_me4u: Decimal | None,
        prev_dist_iou2: Decimal | None,
        prev_dist_uome: Decimal | None
    ) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
        """
        Compute RelativePaths for all three coins.
        
        Returns:
            Tuple of (relpath_me4u, relpath_iou2, relpath_uome)
        """
        return (
            self.compute_relativepath(dist_me4u, prev_dist_me4u),
            self.compute_relativepath(dist_iou2, prev_dist_iou2),
            self.compute_relativepath(dist_uome, prev_dist_uome)
        )
