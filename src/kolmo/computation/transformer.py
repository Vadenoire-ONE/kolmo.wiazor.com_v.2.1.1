"""
Rate Transformer - Convert EUR-based rates to KOLMO notation

🔒 REQ-5.1: Rate transformation MUST use decimal.Decimal type throughout.
🔒 REQ-5.2: Validate dimensional analysis: |K - 1.0| < 0.05
🔒 REQ-5.3: Decimal precision context MUST be set to at least 28 digits.
"""

from decimal import Decimal, getcontext

from kolmo.models import KolmoRates

# 🔒 REQ-5.3: Set decimal precision to 28
getcontext().prec = 28


class RateTransformer:
    """
    Transform EUR-based rates from providers to KOLMO notation.
    
    === KOLMO RATES (Standard Notation) ===
    r_me4u: Decimal  # ME4U coin = USD/CNY (US Dollars per 1 Chinese Yuan)
                     # Example: Decimal('0.1434') means "1 yuan = 0.1434 dollars"
                     # Or equivalently: "1 dollar buys 6.9748 yuan"
    
    r_iou2: Decimal  # IOU2 coin = EUR/USD (Euros per 1 US Dollar)  
                     # Example: Decimal('0.8599') means "1 dollar = 0.8599 euros"
                     # Or equivalently: "1 euro buys 1.163 dollars"
    
    r_uome: Decimal  # UOME coin = CNY/EUR (Chinese Yuan per 1 Euro)
                     # Example: Decimal('8.11') means "1 euro = 8.11 yuan"
                     # Or equivalently: "1 yuan buys 0.1233 euros"
    """
    
    # 🔒 REQ-5.2: Dimensional analysis tolerance
    DIMENSIONAL_TOLERANCE = Decimal("0.05")  # 5%
    
    def transform(
        self,
        eur_usd: Decimal,
        eur_cny: Decimal
    ) -> KolmoRates:
        """
        Transform EUR-based rates to KOLMO notation.
        
        🔒 REQ-5.1: Uses Decimal throughout, never float.
        
        Args:
            eur_usd: EUR/USD rate (e.g., 1.163 means 1 EUR = 1.163 USD)
            eur_cny: EUR/CNY rate (e.g., 8.11 means 1 EUR = 8.11 CNY)
        
        Returns:
            KolmoRates with r_me4u, r_iou2, r_uome
        
        Raises:
            ValueError: If dimensional analysis fails
        """
        # Ensure inputs are Decimal
        eur_usd = self._to_decimal(eur_usd)
        eur_cny = self._to_decimal(eur_cny)
        
        # Step 1: Transform to KOLMO notation
        # IOU2 = USD/EUR = 1 / (EUR/USD)
        r_iou2 = Decimal("1") / eur_usd
        
        # UOME = EUR/CNY means "euros per yuan"
        # Frankfurter: EUR/CNY = 8.11 means 1 EUR = 8.11 CNY
        # So 1 CNY = 1/8.11 EUR → r_uome = 1/eur_cny
        r_uome = Decimal("1") / eur_cny
        
        # ME4U = CNY/USD
        # Using dimensional analysis: CNY/USD = (CNY/EUR) × (EUR/USD)
        # CNY/EUR = eur_cny (since 1 EUR = eur_cny CNY)
        # So: r_me4u = eur_cny / eur_usd... but wait, let me reconsider
        #
        # Actually, ME4U = CNY/USD means "yuan per dollar"
        # If 1 EUR = 1.163 USD and 1 EUR = 8.11 CNY
        # Then 1 USD = 8.11/1.163 CNY = 6.9748 CNY
        # So r_me4u should be CNY/USD = eur_cny / eur_usd
        # But the spec example shows r_me4u = 0.1434 (small number)
        # That means r_me4u is actually USD/CNY-like... 
        #
        # Let me re-read the spec:
        # r_me4u: Decimal  # ME4U coin = CNY/USD (Chinese Yuan per 1 US Dollar)
        #                  # Example: Decimal('0.1434') means "1 yuan = 0.1434 dollars"
        #
        # Wait, 0.1434 means "1 yuan = 0.1434 dollars" which is USD/CNY, not CNY/USD!
        # But the comment says CNY/USD... This is confusing notation.
        #
        # Looking at the example more carefully:
        # r_me4u = 0.1434 with comment "1 yuan = 0.1434 dollars"
        # This means r_me4u represents: how many dollars per yuan = USD/CNY
        #
        # Let's verify with dimensional analysis from spec:
        # K = r_me4u * r_iou2 * r_uome should be ~1
        # 
        # From spec example:
        # r_me4u = 0.1434 (USD/CNY - dollars per yuan)
        # r_iou2 = 0.8599 (EUR/USD - euros per dollar) Wait, spec says USD/EUR
        #
        # I need to look at the exact definitions again:
        # r_iou2: IOU2 coin = USD/EUR (US Dollars per 1 Euro)
        #         Example: 0.8599 means "1 dollar = 0.8599 euros"
        #
        # So 0.8599 means "1 dollar = 0.8599 euros" which is EUR/USD, not USD/EUR!
        # The naming is inverse to the ratio interpretation.
        #
        # Let me use the exact transformation from spec Section 5.1:
        # If Frankfurter gives EUR/USD = 1.163 (1 EUR = 1.163 USD)
        # Then r_iou2 = 1/1.163 = 0.8599
        # This matches the example.
        
        r_me4u = eur_cny / eur_usd  # CNY per USD
        
        # Wait, the spec shows r_me4u = 6.973516294... in Section 5.1 output
        # But in Section 2.1 it shows r_me4u = 0.1434
        # These are inverses! Let me check Section 5.1 again...
        #
        # Section 5.1 output shows:
        # ME4U (CNY/USD): 6.973516294309206963
        # 
        # And dimensional analysis check:
        # kolmo_value = r_me4u * r_iou2 * r_uome
        # = (CNY/USD) * (USD/EUR) * (EUR/CNY) = 1 (dimensionless)
        #
        # So for the dimensional analysis to work:
        # r_me4u = CNY/USD (yuan per dollar) = eur_cny/eur_usd = 8.11/1.163 ≈ 6.97
        # r_iou2 = USD/EUR (dollars per euro) = 1/eur_usd = 1/1.163 ≈ 0.86
        # r_uome = EUR/CNY (euros per yuan) = 1/eur_cny = 1/8.11 ≈ 0.123
        #
        # Check: 6.97 * 0.86 * 0.123 ≈ 0.737 ≠ 1 ... that's wrong!
        #
        # Let me recalculate more carefully:
        # r_me4u = 8.11/1.163 = 6.9734...
        # r_iou2 = 1/1.163 = 0.8599...
        # r_uome = 1/8.11 = 0.1233...
        #
        # Product: 6.9734 * 0.8599 * 0.1233 = 0.739 ≠ 1
        #
        # Something is wrong. Let me re-read the spec transformation...
        #
        # Oh! In Section 5.1, the spec has a comment "Wait - check Frankfurter docs"
        # and then reconsiders the interpretation!
        #
        # The correct interpretation from the end of Section 5.1:
        # r_me4u = eur_cny / eur_usd = 6.973... (CNY per USD)
        # But then the spec says r_uome = 1/eur_cny = 0.123... 
        #
        # Actually wait, looking at the dimensional analysis comment in spec:
        # (CNY/USD) * (USD/EUR) * (EUR/CNY) = CNY * EUR / (USD * EUR * CNY) = 1/USD??
        #
        # That doesn't cancel properly either. Let me think again...
        #
        # For units to cancel to dimensionless:
        # A/B * B/C * C/A = 1 ✓
        #
        # So we need: (CNY/USD) * (USD/EUR) * (EUR/CNY) 
        # = CNY/USD * USD/EUR * EUR/CNY
        # = (CNY * USD * EUR) / (USD * EUR * CNY)
        # = 1 ✓
        #
        # OK so the dimensions are correct. The issue is my calculation.
        #
        # Let me use exact values:
        # eur_usd = 1.163 (1 EUR = 1.163 USD)
        # eur_cny = 8.11 (1 EUR = 8.11 CNY)
        #
        # r_me4u = CNY/USD = ? 
        # 1 USD = 1/1.163 EUR
        # 1 EUR = 8.11 CNY
        # So 1 USD = 8.11/1.163 CNY = 6.9734 CNY
        # Therefore CNY/USD = 1/6.9734 = 0.1434 ✓
        # Wait no, if 1 USD = 6.9734 CNY, then CNY/USD = 6.9734!
        #
        # Hmm, CNY/USD can mean two things:
        # 1. "How many CNY per 1 USD" = 6.9734
        # 2. "CNY expressed in USD units" = 1/6.9734 = 0.1434
        #
        # Looking at spec again: "Example: Decimal('0.1434') means '1 yuan = 0.1434 dollars'"
        # So 1 CNY = 0.1434 USD
        # This is actually USD per CNY, i.e., USD/CNY = 0.1434
        # The notation CNY/USD in the spec comment seems to be... inverted?
        #
        # Let me just follow the spec code exactly from Section 5.1:
        
        # From spec Section 5.1 Example code (corrected version):
        # r_iou2 = 1 / eur_usd = 0.8599...
        # r_uome = 1 / eur_cny = 0.1233...
        # r_me4u = eur_cny / eur_usd = 6.9735...
        #
        # Product: 6.9735 * 0.8599 * 0.1233 = 0.739 ≈ not 1!
        #
        # The spec output shows KOLMO: 1.000041342600000000
        # So the spec example must have different input values or calculations.
        #
        # Let me trace through spec Section 2.2 Example:
        # r_me4u = Decimal('0.1434')   # CNY/USD
        # r_iou2 = Decimal('0.8599')   # USD/EUR  
        # r_uome = Decimal('8.11')     # EUR/CNY
        # kolmo_value = r_me4u * r_iou2 * r_uome = 0.1434 * 0.8599 * 8.11 = 1.0000413...
        #
        # So in that example:
        # r_me4u = 0.1434 (this is actually USD/CNY conceptually)
        # r_iou2 = 0.8599 (this is EUR/USD conceptually)  
        # r_uome = 8.11 (this is CNY/EUR conceptually)
        #
        # The dimensional analysis: (USD/CNY) * (EUR/USD) * (CNY/EUR) = 1 ✓
        #
        # So the transformation should be:
        # r_me4u = 1 / (eur_cny / eur_usd) = eur_usd / eur_cny
        # r_iou2 = 1 / eur_usd
        # r_uome = eur_cny
        
        # Calculate correctly based on spec examples
        r_me4u = eur_usd / eur_cny  # ~0.1434 when eur_usd=1.163, eur_cny=8.11
        r_iou2 = Decimal("1") / eur_usd  # ~0.8599
        r_uome = eur_cny  # 8.11
        
        # Step 2: Validate dimensional analysis
        kolmo_value = r_me4u * r_iou2 * r_uome
        deviation = abs(kolmo_value - Decimal("1.0"))
        
        if deviation > self.DIMENSIONAL_TOLERANCE:
            raise ValueError(
                f"🔒 Dimensional analysis failed: K = {kolmo_value}, "
                f"deviation = {deviation} > {self.DIMENSIONAL_TOLERANCE}"
            )
        
        return KolmoRates(
            r_me4u=r_me4u,
            r_iou2=r_iou2,
            r_uome=r_uome
        )
    
    def _to_decimal(self, value) -> Decimal:
        """🔒 REQ-2.1: Convert to exact Decimal."""
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))
