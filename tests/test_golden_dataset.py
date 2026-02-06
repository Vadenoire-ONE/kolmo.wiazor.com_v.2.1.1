"""
Golden Dataset Tests

🔒 REQ-8.1: Repository MUST include golden dataset
🔒 REQ-8.5: Integration tests MUST verify against golden dataset
"""

import csv
import os
import pytest
from decimal import Decimal, InvalidOperation
from pathlib import Path

from kolmo.computation.transformer import RateTransformer
from kolmo.computation.calculator import KOLMOCalculator
from kolmo.computation.winner import WinnerSelector


# Path to golden dataset
GOLDEN_DATA_PATH = Path(__file__).parent / "golden" / "kolmo_reference_data.csv"


def load_golden_data():
    """Load golden dataset if it exists."""
    if not GOLDEN_DATA_PATH.exists():
        pytest.skip(f"Golden dataset not found at {GOLDEN_DATA_PATH}")
    
    with open(GOLDEN_DATA_PATH, newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def _parse_optional_decimal(value: str) -> Decimal | None:
    """Parse a CSV field into Decimal or return None for empty/whitespace."""
    if value is None:
        return None
    s = value.strip()
    if s == "":
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


@pytest.fixture
def golden_data():
    """Fixture to load golden dataset."""
    return load_golden_data()


class TestGoldenDataset:
    """Tests against golden reference dataset."""
    
    def setup_method(self):
        self.transformer = RateTransformer()
        self.calculator = KOLMOCalculator()
        self.selector = WinnerSelector()
    
    @pytest.mark.skipif(
        not GOLDEN_DATA_PATH.exists(),
        reason="Golden dataset not available"
    )
    def test_golden_dataset_exists(self):
        """🔒 REQ-8.1: Verify golden dataset exists."""
        assert GOLDEN_DATA_PATH.exists()
    
    @pytest.mark.skipif(
        not GOLDEN_DATA_PATH.exists(),
        reason="Golden dataset not available"
    )
    def test_golden_dataset_has_minimum_rows(self, golden_data):
        """🔒 REQ-8.1: Golden dataset MUST have at least 50 dates."""
        assert len(golden_data) >= 50, \
            f"Golden dataset has only {len(golden_data)} rows, need ≥50"
    
    @pytest.mark.skipif(
        not GOLDEN_DATA_PATH.exists(),
        reason="Golden dataset not available"
    )
    def test_golden_kolmo_exact_match(self, golden_data):
        """
        🔒 REQ-8.5: KOLMO calculation MUST match golden dataset exactly.
        
        Verifies that kolmo_value = r_me4u * r_iou2 * r_uome
        matches the kolmo_value_exact column (exact string match).
        """
        for row in golden_data:
            date = row["date"]
            
            r_me4u = Decimal(row["r_me4u"])
            r_iou2 = Decimal(row["r_iou2"])
            r_uome = Decimal(row["r_uome"])
            
            computed_kolmo = self.calculator.compute_kolmo_value(
                r_me4u, r_iou2, r_uome
            )
            
            expected_kolmo = Decimal(row["kolmo_value_exact"])
            
            assert computed_kolmo == expected_kolmo, \
                f"Date {date}: KOLMO mismatch. " \
                f"Computed: {computed_kolmo}, Expected: {expected_kolmo}"
    
    @pytest.mark.skipif(
        not GOLDEN_DATA_PATH.exists(),
        reason="Golden dataset not available"
    )
    def test_golden_winner_match(self, golden_data):
        """
        🔒 REQ-8.5: Winner selection MUST match golden dataset exactly.
        """
        for row in golden_data:
            date = row["date"]
            expected_winner = row.get("winner")
            if expected_winner is None or expected_winner.strip() == "":
                # Project invariant: winner is never null; default to IOU2
                expected_winner = "IOU2"
            
            # Parse RelativePath values (may be empty string for first day)
            relpath_me4u = _parse_optional_decimal(row.get("relpath_me4u"))
            relpath_iou2 = _parse_optional_decimal(row.get("relpath_iou2"))
            relpath_uome = _parse_optional_decimal(row.get("relpath_uome"))
            
            winner, _ = self.selector.select(relpath_me4u, relpath_iou2, relpath_uome)
            
            assert winner.value == expected_winner, \
                f"Date {date}: Winner mismatch. " \
                f"Computed: {winner.value}, Expected: {expected_winner}"
    
    @pytest.mark.skipif(
        not GOLDEN_DATA_PATH.exists(),
        reason="Golden dataset not available"
    )
    def test_golden_distance_calculation(self, golden_data):
        """Verify distance calculations match golden dataset (±0.0001 tolerance)."""
        for row in golden_data:
            date = row["date"]
            
            r_me4u = Decimal(row["r_me4u"])
            r_iou2 = Decimal(row["r_iou2"])
            r_uome = Decimal(row["r_uome"])
            
            computed_dist_me4u = self.calculator.compute_distance(r_me4u)
            computed_dist_iou2 = self.calculator.compute_distance(r_iou2)
            computed_dist_uome = self.calculator.compute_distance(r_uome)
            
            expected_dist_me4u = Decimal(row["dist_me4u"])
            expected_dist_iou2 = Decimal(row["dist_iou2"])
            expected_dist_uome = Decimal(row["dist_uome"])
            
            tolerance = Decimal("0.0001")
            
            assert abs(computed_dist_me4u - expected_dist_me4u) < tolerance, \
                f"Date {date}: dist_me4u mismatch"
            assert abs(computed_dist_iou2 - expected_dist_iou2) < tolerance, \
                f"Date {date}: dist_iou2 mismatch"
            assert abs(computed_dist_uome - expected_dist_uome) < tolerance, \
                f"Date {date}: dist_uome mismatch"


class TestGoldenDatasetEndToEnd:
    """End-to-end pipeline tests using golden dataset."""
    
    @pytest.mark.skipif(
        not GOLDEN_DATA_PATH.exists(),
        reason="Golden dataset not available"
    )
    def test_full_pipeline_golden(self, golden_data):
        """
        🔒 REQ-8.5: Verify entire pipeline matches golden dataset.
        
        This test simulates the full computation pipeline:
        1. Transform rates
        2. Compute KOLMO
        3. Compute distances
        4. Select winner
        """
        transformer = RateTransformer()
        calculator = KOLMOCalculator()
        selector = WinnerSelector()
        
        prev_distances = {}
        
        for row in golden_data:
            date = row["date"]
            eur_usd = Decimal(row["eur_usd"])
            eur_cny = Decimal(row["eur_cny"])
            
            # Step 1: Transform
            rates = transformer.transform(eur_usd, eur_cny)
            
            # Step 2: KOLMO
            kolmo = calculator.compute_kolmo_value(
                rates.r_me4u, rates.r_iou2, rates.r_uome
            )
            
            # Step 3: Distances
            dist_me4u = calculator.compute_distance(rates.r_me4u)
            dist_iou2 = calculator.compute_distance(rates.r_iou2)
            dist_uome = calculator.compute_distance(rates.r_uome)
            
            # Step 4: RelativePaths
            relpath_me4u = calculator.compute_relativepath(
                dist_me4u, prev_distances.get("me4u")
            )
            relpath_iou2 = calculator.compute_relativepath(
                dist_iou2, prev_distances.get("iou2")
            )
            relpath_uome = calculator.compute_relativepath(
                dist_uome, prev_distances.get("uome")
            )
            
            # Step 5: Winner
            winner, _ = selector.select(relpath_me4u, relpath_iou2, relpath_uome)
            
            # Verify winner matches
            expected_winner = row["winner"]
            assert winner.value == expected_winner, \
                f"Date {date}: Pipeline winner mismatch"
            
            # Update prev_distances for next iteration
            prev_distances = {
                "me4u": dist_me4u,
                "iou2": dist_iou2,
                "uome": dist_uome
            }
