#!/usr/bin/env python3
"""
repair_deviation.py
-------------------
Recalculate kolmo_deviation for entries where it was stored as 0
due to computing K from exact (pre-rounding) rates instead of
stored (rounded-to-6-decimal) rates.

Also recalculates distance, relpath, volatility, and winner for
affected entries for full consistency.
"""

import json
import shutil
from decimal import Decimal
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "export"
KOLMO_PATH = DATA_DIR / "kolmo_history.json"

# Threshold: entries with deviation exactly "0.000000000000000000e-5" are broken
ZERO_DEVIATION = "0.000000000000000000e-5"


def format_deviation(kolmo_value: Decimal) -> str:
    deviation = kolmo_value - Decimal("1.0")
    return f"{float(deviation) * 1e5:.18f}e-5"


def format_rate(rate: Decimal) -> str:
    return f"{float(rate):.6f}"


def compute_distance(rate: Decimal) -> Decimal:
    return abs(rate - Decimal("1"))


def compute_relpath(dist_curr: Decimal, dist_prev: Decimal) -> Decimal | None:
    if dist_prev == Decimal("0"):
        return None
    return (dist_curr - dist_prev) / dist_prev


def compute_volatility(rate_curr: Decimal, rate_prev: Decimal) -> float:
    if rate_prev == Decimal("0"):
        return 0.0
    return float((rate_curr - rate_prev) / rate_prev * Decimal("100"))


def select_winner(rp_me4u, rp_iou2, rp_uome) -> str:
    """Determine winner from relative paths (same logic as update_kolmo_history)."""
    candidates = {
        "ME4U": rp_me4u,
        "IOU2": rp_iou2,
        "UOME": rp_uome,
    }
    valid = {k: v for k, v in candidates.items() if v is not None}
    if not valid:
        return "ME4U"  # default
    # Winner: the one with the SMALLEST absolute relpath
    return min(valid, key=lambda k: abs(valid[k]))


def main():
    print(f"Loading {KOLMO_PATH} ...")
    kolmo = json.loads(KOLMO_PATH.read_text(encoding="utf-8"))
    print(f"Total entries: {len(kolmo)}")

    # Find broken entries
    broken_indices = []
    for i, entry in enumerate(kolmo):
        if entry.get("kolmo_deviation") == ZERO_DEVIATION:
            broken_indices.append(i)

    if not broken_indices:
        print("No broken entries found. Nothing to repair.")
        return

    print(f"Found {len(broken_indices)} entries with zero deviation.")
    print(f"  First: index {broken_indices[0]}, date {kolmo[broken_indices[0]]['date']}")
    print(f"  Last:  index {broken_indices[-1]}, date {kolmo[broken_indices[-1]]['date']}")

    # We need to recalculate from the first broken entry.
    # The entry BEFORE the first broken one provides the prev_ctx.
    start_idx = broken_indices[0]

    # Get prev_ctx from entry before the first broken one
    if start_idx > 0:
        prev = kolmo[start_idx - 1]
        r_me4u_prev = Decimal(prev["r_me4u"])
        r_iou2_prev = Decimal(prev["r_iou2"])
        r_uome_prev = Decimal(prev["r_uome"])
        prev_ctx = {
            "r_me4u": r_me4u_prev,
            "r_iou2": r_iou2_prev,
            "r_uome": r_uome_prev,
            "dist_me4u": compute_distance(r_me4u_prev),
            "dist_iou2": compute_distance(r_iou2_prev),
            "dist_uome": compute_distance(r_uome_prev),
        }
    else:
        # First entry, no prev context
        prev_ctx = {
            "r_me4u": Decimal("1"),
            "r_iou2": Decimal("1"),
            "r_uome": Decimal("1"),
            "dist_me4u": Decimal("0"),
            "dist_iou2": Decimal("0"),
            "dist_uome": Decimal("0"),
        }

    # Recalculate from start_idx onwards
    repaired = 0
    for i in range(start_idx, len(kolmo)):
        entry = kolmo[i]

        # Rates are already stored rounded in the JSON
        r_me4u = Decimal(entry["r_me4u"])
        r_iou2 = Decimal(entry["r_iou2"])
        r_uome = Decimal(entry["r_uome"])

        # KOLMO invariant from stored (rounded) rates
        kolmo_value = r_me4u * r_iou2 * r_uome
        new_deviation = format_deviation(kolmo_value)

        # Distances
        dist_me4u = compute_distance(r_me4u)
        dist_iou2 = compute_distance(r_iou2)
        dist_uome = compute_distance(r_uome)

        # Relpaths
        rp_me4u = compute_relpath(dist_me4u, prev_ctx["dist_me4u"])
        rp_iou2 = compute_relpath(dist_iou2, prev_ctx["dist_iou2"])
        rp_uome = compute_relpath(dist_uome, prev_ctx["dist_uome"])

        # Winner
        winner = select_winner(rp_me4u, rp_iou2, rp_uome)

        # Volatility
        vol_me4u = compute_volatility(r_me4u, prev_ctx["r_me4u"])
        vol_iou2 = compute_volatility(r_iou2, prev_ctx["r_iou2"])
        vol_uome = compute_volatility(r_uome, prev_ctx["r_uome"])

        old_deviation = entry.get("kolmo_deviation", "N/A")
        old_winner = entry.get("winner", "N/A")

        # Update entry
        entry["kolmo_deviation"] = new_deviation
        entry["relpath_me4u"] = round(float(rp_me4u), 4) if rp_me4u is not None else None
        entry["relpath_iou2"] = round(float(rp_iou2), 4) if rp_iou2 is not None else None
        entry["relpath_uome"] = round(float(rp_uome), 4) if rp_uome is not None else None
        entry["vol_me4u"] = vol_me4u
        entry["vol_iou2"] = vol_iou2
        entry["vol_uome"] = vol_uome
        entry["winner"] = winner

        changed = (old_deviation != new_deviation or old_winner != winner)
        if changed:
            repaired += 1
            print(f"  🔧 {entry['date']}: deviation {old_deviation} → {new_deviation}"
                  f"{' winner: ' + old_winner + '→' + winner if old_winner != winner else ''}")

        # Update prev context
        prev_ctx = {
            "r_me4u": r_me4u,
            "r_iou2": r_iou2,
            "r_uome": r_uome,
            "dist_me4u": dist_me4u,
            "dist_iou2": dist_iou2,
            "dist_uome": dist_uome,
        }

    print(f"\nRepaired {repaired} entries (recalculated {len(kolmo) - start_idx} total from {kolmo[start_idx]['date']}).")

    # Backup & save
    bak = KOLMO_PATH.with_suffix(KOLMO_PATH.suffix + ".bak")
    print(f"Backing up → {bak}")
    shutil.copy2(KOLMO_PATH, bak)

    print(f"Writing {len(kolmo)} entries to {KOLMO_PATH} ...")
    KOLMO_PATH.write_text(
        json.dumps(kolmo, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("✅ Done.")


if __name__ == "__main__":
    main()
