"""
Winner Selector - Select daily KOLMO winner coin

🔒 REQ-2.5: Winner MUST be selected from coins with relpath > 0.
🔒 REQ-2.6: Tie-break alphabetically: IOU2 < ME4U < UOME.
🔒 REQ-5.7-5.9: Winner selection rules and explainability.
"""

from decimal import Decimal

from kolmo.models import WinnerCoin, WinnerReason, SelectionRule


class WinnerSelector:
    """
    Select KOLMO Winner coin based on RelativePath values.
    
    Selection Rules (in order):
    1. Choose coin with highest POSITIVE RelativePath
    2. If multiple coins tie, alphabetical order: IOU2 < ME4U < UOME
    3. If all RelativePath are negative/zero, choose least negative
    4. If all RelativePath are NULL, choose IOU2 (default)
    """
    
    # 🔒 REQ-2.6: Alphabetical order for tie-break
    ALPHABETICAL_ORDER = ["IOU2", "ME4U", "UOME"]
    
    def select(
        self,
        relpath_me4u: Decimal | None,
        relpath_iou2: Decimal | None,
        relpath_uome: Decimal | None
    ) -> tuple[WinnerCoin, WinnerReason]:
        """
        🔒 REQ-5.7: Select winner using priority rules.
        
        Args:
            relpath_me4u: ME4U RelativePath (None if first day)
            relpath_iou2: IOU2 RelativePath (None if first day)
            relpath_uome: UOME RelativePath (None if first day)
        
        Returns:
            Tuple of (winner_coin, winner_reason_json)
        """
        # Build candidate dictionary (exclude NULL values)
        candidates: dict[str, Decimal] = {}
        
        if relpath_me4u is not None:
            candidates["ME4U"] = relpath_me4u
        if relpath_iou2 is not None:
            candidates["IOU2"] = relpath_iou2
        if relpath_uome is not None:
            candidates["UOME"] = relpath_uome
        
        # 🔒 Case 1: All NULL (first day in dataset)
        if not candidates:
            return WinnerCoin.IOU2, WinnerReason(
                me4u_relpath=None,
                iou2_relpath=None,
                uome_relpath=None,
                max_relpath=None,
                tied_coins=[],
                selection_rule=SelectionRule.DEFAULT_FIRST_DAY,
                winner=WinnerCoin.IOU2
            )
        
        # Find maximum RelativePath
        max_relpath = max(candidates.values())
        
        # Get all coins with max value (handle ties)
        tied_coins = sorted([
            coin for coin, rp in candidates.items()
            if rp == max_relpath
        ])
        
        # 🔒 REQ-2.6: Winner is first in alphabetical order
        winner_str = tied_coins[0]
        winner = WinnerCoin(winner_str)
        
        # Determine selection rule
        if max_relpath > Decimal("0"):
            rule = SelectionRule.MAX_POSITIVE_ALPHABETICAL_TIEBREAK
        else:
            rule = SelectionRule.LEAST_NEGATIVE
        
        # 🔒 REQ-5.9: Build explainability JSON
        reason = WinnerReason(
            me4u_relpath=float(relpath_me4u) if relpath_me4u is not None else None,
            iou2_relpath=float(relpath_iou2) if relpath_iou2 is not None else None,
            uome_relpath=float(relpath_uome) if relpath_uome is not None else None,
            max_relpath=float(max_relpath),
            tied_coins=tied_coins,
            selection_rule=rule,
            winner=winner
        )
        
        return winner, reason
