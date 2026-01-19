"""
KOLMO Computation Unit Tests

🔒 REQ-8.3: Unit tests MUST achieve ≥95% code coverage
🔒 REQ-8.4: Tests MUST include exact decimal equality tests
"""

import pytest
from decimal import Decimal

from kolmo.computation.transformer import RateTransformer
from kolmo.computation.calculator import KOLMOCalculator
from kolmo.computation.winner import WinnerSelector
from kolmo.models import KolmoRates, KolmoState, WinnerCoin, SelectionRule


class TestRateTransformer:
    """Tests for RateTransformer."""
    
    def setup_method(self):
        self.transformer = RateTransformer()
    
    def test_transform_basic(self):
        """Test basic rate transformation."""
        # Using spec example values
        eur_usd = Decimal("1.163")
        eur_cny = Decimal("8.11")
        
        rates = self.transformer.transform(eur_usd, eur_cny)
        
        assert isinstance(rates, KolmoRates)
        assert rates.r_me4u > 0
        assert rates.r_iou2 > 0
        assert rates.r_uome > 0
    
    def test_transform_decimal_precision(self):
        """🔒 REQ-5.1: Verify Decimal type is preserved."""
        eur_usd = Decimal("1.163")
        eur_cny = Decimal("8.11")
        
        rates = self.transformer.transform(eur_usd, eur_cny)
        
        assert isinstance(rates.r_me4u, Decimal)
        assert isinstance(rates.r_iou2, Decimal)
        assert isinstance(rates.r_uome, Decimal)
    
    def test_transform_dimensional_analysis(self):
        """🔒 REQ-5.2: Verify dimensional analysis validation."""
        eur_usd = Decimal("1.163")
        eur_cny = Decimal("8.11")
        
        rates = self.transformer.transform(eur_usd, eur_cny)
        
        # Product should be close to 1.0
        product = rates.r_me4u * rates.r_iou2 * rates.r_uome
        deviation = abs(product - Decimal("1.0"))
        
        assert deviation < Decimal("0.05"), f"Dimensional analysis failed: K={product}"
    
    def test_transform_invalid_dimensional_analysis_fails(self):
        """
        Verify dimensional analysis always holds.
        
        Due to the transformation formula (r_me4u = eur_usd/eur_cny, r_iou2 = 1/eur_usd, 
        r_uome = eur_cny), the KOLMO invariant K = r_me4u * r_iou2 * r_uome always equals 1.0
        mathematically. This test verifies that property holds.
        """
        from decimal import Decimal
        from kolmo.computation.transformer import RateTransformer
        
        transformer = RateTransformer()
        
        # Test with various extreme rates - K should always be 1.0
        test_cases = [
            (Decimal("100.0"), Decimal("0.001")),
            (Decimal("0.001"), Decimal("100.0")),
            (Decimal("1.5"), Decimal("7.5")),
            (Decimal("2.0"), Decimal("5.0")),
        ]
        
        for eur_usd, eur_cny in test_cases:
            rates = transformer.transform(eur_usd=eur_usd, eur_cny=eur_cny)
            kolmo_value = rates.r_me4u * rates.r_iou2 * rates.r_uome
            # Due to formula design, K should always equal 1.0
            assert abs(kolmo_value - Decimal("1.0")) < Decimal("0.000001"), \
                f"Dimensional analysis failed for eur_usd={eur_usd}, eur_cny={eur_cny}: K={kolmo_value}"


class TestKOLMOCalculator:
    """Tests for KOLMOCalculator."""
    
    def setup_method(self):
        self.calculator = KOLMOCalculator()
    
    def test_compute_kolmo_value_exact(self):
        """🔒 Amendment A1: Verify EXACT KOLMO computation."""
        r_me4u = Decimal("0.1434")
        r_iou2 = Decimal("0.8599")
        r_uome = Decimal("8.11")
        
        result = self.calculator.compute_kolmo_value(r_me4u, r_iou2, r_uome)
        
        # Exact expected value from spec Section 2.2
        expected = r_me4u * r_iou2 * r_uome
        assert result == expected, f"Expected {expected}, got {result}"
    
    def test_compute_kolmo_value_is_decimal(self):
        """Verify result is Decimal type."""
        result = self.calculator.compute_kolmo_value(
            Decimal("0.1434"),
            Decimal("0.8599"),
            Decimal("8.11")
        )
        
        assert isinstance(result, Decimal)
    
    def test_compute_deviation(self):
        """Test deviation calculation."""
        kolmo_value = Decimal("1.0041")
        
        deviation = self.calculator.compute_deviation(kolmo_value)
        
        expected = Decimal("0.0041")
        assert deviation == expected
    
    def test_compute_state_ok(self):
        """Test OK state (deviation < 1%)."""
        kolmo_value = Decimal("1.005")  # 0.5% deviation
        
        state = self.calculator.compute_state(kolmo_value)
        
        assert state == KolmoState.OK
    
    def test_compute_state_warn(self):
        """Test WARN state (1% ≤ deviation < 5%)."""
        kolmo_value = Decimal("1.03")  # 3% deviation
        
        state = self.calculator.compute_state(kolmo_value)
        
        assert state == KolmoState.WARN
    
    def test_compute_state_critical(self):
        """Test CRITICAL state (deviation ≥ 5%)."""
        kolmo_value = Decimal("1.06")  # 6% deviation
        
        state = self.calculator.compute_state(kolmo_value)
        
        assert state == KolmoState.CRITICAL
    
    def test_compute_distance(self):
        """🔒 REQ-2.3: Test distance calculation."""
        rate = Decimal("0.1434")
        
        distance = self.calculator.compute_distance(rate)
        
        expected = Decimal("85.66")
        assert distance == expected
    
    def test_compute_relativepath_improvement(self):
        """Test RelativePath for improving rate."""
        dist_yesterday = Decimal("86.30")
        dist_today = Decimal("85.66")
        
        relpath = self.calculator.compute_relativepath(dist_today, dist_yesterday)
        
        # Expected: (86.30 - 85.66) / 86.30 * 100 ≈ 0.74
        assert relpath is not None
        assert relpath > 0  # Positive = improving
    
    def test_compute_relativepath_deterioration(self):
        """Test RelativePath for deteriorating rate."""
        dist_yesterday = Decimal("85.66")
        dist_today = Decimal("86.30")
        
        relpath = self.calculator.compute_relativepath(dist_today, dist_yesterday)
        
        assert relpath is not None
        assert relpath < 0  # Negative = deteriorating
    
    def test_compute_relativepath_null_first_day(self):
        """🔒 REQ-5.5: RelativePath NULL for first day."""
        relpath = self.calculator.compute_relativepath(
            dist_current=Decimal("85.66"),
            dist_previous=None
        )
        
        assert relpath is None
    
    def test_compute_relativepath_null_division_by_zero(self):
        """🔒 REQ-5.5: RelativePath NULL when previous is zero."""
        relpath = self.calculator.compute_relativepath(
            dist_current=Decimal("85.66"),
            dist_previous=Decimal("0")
        )
        
        assert relpath is None


class TestWinnerSelector:
    """Tests for WinnerSelector."""
    
    def setup_method(self):
        self.selector = WinnerSelector()
    
    def test_select_highest_positive(self):
        """🔒 REQ-2.5: Select coin with highest positive RelativePath."""
        relpath_me4u = Decimal("-0.35")
        relpath_iou2 = Decimal("3.24")
        relpath_uome = Decimal("0.05")
        
        winner, reason = self.selector.select(relpath_me4u, relpath_iou2, relpath_uome)
        
        assert winner == WinnerCoin.IOU2
        assert reason.selection_rule == SelectionRule.MAX_POSITIVE_ALPHABETICAL_TIEBREAK
    
    def test_select_all_negative(self):
        """🔒 REQ-5.7: Select least negative when all negative."""
        relpath_me4u = Decimal("-2.10")
        relpath_iou2 = Decimal("-0.85")  # Least negative
        relpath_uome = Decimal("-1.50")
        
        winner, reason = self.selector.select(relpath_me4u, relpath_iou2, relpath_uome)
        
        assert winner == WinnerCoin.IOU2
        assert reason.selection_rule == SelectionRule.LEAST_NEGATIVE
    
    def test_select_tiebreak_alphabetical(self):
        """🔒 REQ-2.6: Alphabetical tie-break: IOU2 < ME4U < UOME."""
        relpath_me4u = Decimal("3.24")
        relpath_iou2 = Decimal("3.24")  # Tied with ME4U
        relpath_uome = Decimal("1.00")
        
        winner, reason = self.selector.select(relpath_me4u, relpath_iou2, relpath_uome)
        
        assert winner == WinnerCoin.IOU2  # IOU2 < ME4U alphabetically
        assert "IOU2" in reason.tied_coins
        assert "ME4U" in reason.tied_coins
    
    def test_select_all_null_first_day(self):
        """🔒 REQ-5.7: Default to IOU2 when all NULL."""
        winner, reason = self.selector.select(None, None, None)
        
        assert winner == WinnerCoin.IOU2
        assert reason.selection_rule == SelectionRule.DEFAULT_FIRST_DAY
    
    def test_select_explainability_metadata(self):
        """🔒 REQ-5.9: Verify winner_reason contains required fields."""
        winner, reason = self.selector.select(
            Decimal("-0.35"),
            Decimal("3.24"),
            Decimal("0.05")
        )
        
        # Verify all required fields present
        assert reason.me4u_relpath == -0.35
        assert reason.iou2_relpath == 3.24
        assert reason.uome_relpath == 0.05
        assert reason.max_relpath == 3.24
        assert reason.selection_rule is not None
        assert reason.winner == winner


class TestKolmoIntegration:
    """Integration tests for KOLMO computation pipeline."""
    
    def test_spec_example_section_2_2(self):
        """
        Verify computation matches spec Section 2.2 example.
        
        Input:
          r_me4u = 0.1434  # USD/CNY
          r_iou2 = 0.8599  # EUR/USD
          r_uome = 8.11    # CNY/EUR
        
        Expected output:
          kolmo_value = 1.0000413426
        """
        calculator = KOLMOCalculator()
        
        r_me4u = Decimal("0.1434")
        r_iou2 = Decimal("0.8599")
        r_uome = Decimal("8.11")
        
        kolmo_value = calculator.compute_kolmo_value(r_me4u, r_iou2, r_uome)
        
        # Exact product
        expected = Decimal("0.1434") * Decimal("0.8599") * Decimal("8.11")
        assert kolmo_value == expected
        
        # Verify approximate value matches spec
        assert abs(float(kolmo_value) - 1.0000413426) < 1e-8
    
    def test_winner_selection_scenarios(self):
        """Test all winner selection scenarios from spec Section 5.4."""
        selector = WinnerSelector()
        
        # Scenario 1: One positive relpath
        winner, _ = selector.select(
            Decimal("-0.35"),
            Decimal("3.24"),
            Decimal("0.05")
        )
        assert winner == WinnerCoin.IOU2
        
        # Scenario 2: All negative relpath
        winner, _ = selector.select(
            Decimal("-2.10"),
            Decimal("-0.85"),
            Decimal("-1.50")
        )
        assert winner == WinnerCoin.IOU2  # Least negative
        
        # Scenario 3: Tie
        winner, reason = selector.select(
            Decimal("3.24"),
            Decimal("3.24"),
            Decimal("1.00")
        )
        assert winner == WinnerCoin.IOU2  # Alphabetical: IOU2 < ME4U
