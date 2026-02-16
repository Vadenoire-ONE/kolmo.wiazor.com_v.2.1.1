#!/usr/bin/env python3
"""
Regenerate golden dataset using the actual KOLMO pipeline.

Ensures internal mathematical consistency:
- r_me4u, r_iou2, r_uome from RateTransformer (K = 1 exactly)
- kolmo_value_exact = exact product of stored rates
- distances, relpaths, winners from Calculator + Selector
"""

import csv
import sys
from decimal import Decimal, getcontext
from pathlib import Path

getcontext().prec = 28

# Add src to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from kolmo.computation.transformer import RateTransformer
from kolmo.computation.calculator import KOLMOCalculator
from kolmo.computation.winner import WinnerSelector

GOLDEN_CSV = ROOT / "tests" / "golden" / "kolmo_reference_data.csv"


def main():
    transformer = RateTransformer()
    calculator = KOLMOCalculator()
    selector = WinnerSelector()

    # Read existing CSV for eur_* source values
    with open(GOLDEN_CSV, newline="") as f:
        old_rows = list(csv.DictReader(f))

    print(f"Read {len(old_rows)} rows from golden CSV")

    new_rows = []
    prev_dist = {}

    for i, old in enumerate(old_rows):
        eu = Decimal(old["eur_usd"])
        ec = Decimal(old["eur_cny"])

        # Step 1: Transform (DTKT internal math — K = 1 exactly)
        rates = transformer.transform(eu, ec)

        # Step 2: KOLMO invariant (product of rates)
        kolmo = calculator.compute_kolmo_value(
            rates.r_me4u, rates.r_iou2, rates.r_uome
        )

        # Step 3: Distances
        d_me4u = calculator.compute_distance(rates.r_me4u)
        d_iou2 = calculator.compute_distance(rates.r_iou2)
        d_uome = calculator.compute_distance(rates.r_uome)

        # Step 4: RelativePaths
        rp_me4u = calculator.compute_relativepath(d_me4u, prev_dist.get("me4u"))
        rp_iou2 = calculator.compute_relativepath(d_iou2, prev_dist.get("iou2"))
        rp_uome = calculator.compute_relativepath(d_uome, prev_dist.get("uome"))

        # Step 5: Winner
        winner, reason = selector.select(rp_me4u, rp_iou2, rp_uome)

        new_rows.append({
            "date": old["date"],
            "eur_usd": old["eur_usd"],
            "eur_cny": old["eur_cny"],
            "eur_rub": old.get("eur_rub", ""),
            "eur_inr": old.get("eur_inr", ""),
            "eur_aed": old.get("eur_aed", ""),
            "r_me4u": str(rates.r_me4u),
            "r_iou2": str(rates.r_iou2),
            "r_uome": str(rates.r_uome),
            "kolmo_value_exact": str(kolmo),
            "dist_me4u": str(d_me4u),
            "dist_iou2": str(d_iou2),
            "dist_uome": str(d_uome),
            "relpath_me4u": str(rp_me4u) if rp_me4u is not None else "",
            "relpath_iou2": str(rp_iou2) if rp_iou2 is not None else "",
            "relpath_uome": str(rp_uome) if rp_uome is not None else "",
            "winner": winner.value,
        })

        prev_dist = {"me4u": d_me4u, "iou2": d_iou2, "uome": d_uome}

    # Write regenerated CSV
    fieldnames = [
        "date", "eur_usd", "eur_cny", "eur_rub", "eur_inr", "eur_aed",
        "r_me4u", "r_iou2", "r_uome", "kolmo_value_exact",
        "dist_me4u", "dist_iou2", "dist_uome",
        "relpath_me4u", "relpath_iou2", "relpath_uome", "winner",
    ]
    with open(GOLDEN_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(new_rows)

    print(f"Wrote {len(new_rows)} rows to golden CSV")

    # Verification
    for idx in [0, 1, 2, len(new_rows) - 1]:
        r = new_rows[idx]
        print(f"  [{idx}] {r['date']}: K={r['kolmo_value_exact']}, winner={r['winner']}")


if __name__ == "__main__":
    main()
