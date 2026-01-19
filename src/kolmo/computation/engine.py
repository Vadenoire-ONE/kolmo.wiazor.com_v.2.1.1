"""
Computation Engine - Orchestrate KOLMO metric computation

🔒 REQ-3.1: Four-stage pipeline implementation
🔒 REQ-3.2: Computation MUST NOT start until raw data is persisted
"""

import logging
from datetime import date as date_type
from decimal import Decimal
from uuid import UUID, uuid4

from kolmo.computation.transformer import RateTransformer
from kolmo.computation.calculator import KOLMOCalculator
from kolmo.computation.winner import WinnerSelector
from kolmo.database import get_connection
from kolmo.models import (
    ComputeDataCreate,
    ExternalDataCreate,
    KolmoRates,
    WinnerReason,
)

logger = logging.getLogger(__name__)


class ComputationEngine:
    """
    Orchestrates the complete KOLMO computation pipeline.
    
    Stage 3: COMPUTATION ENGINE
    ├─ Rate Transformer (EUR-based → KOLMO notation)
    ├─ KOLMO Calculator (exact decimal product)
    ├─ Distance Calculator (deviation from parity)
    ├─ RelativePath Calculator (improvement tracking)
    └─ Winner Selector (max positive relpath)
    """
    
    def __init__(self):
        self.transformer = RateTransformer()
        self.calculator = KOLMOCalculator()
        self.winner_selector = WinnerSelector()
    
    async def compute_daily_metrics(
        self,
        external_data: ExternalDataCreate
    ) -> ComputeDataCreate:
        """
        🔒 REQ-3.2: Compute all KOLMO metrics from raw external data.
        
        This method assumes external data is already persisted (Stage 2 complete).
        
        Args:
            external_data: Raw provider data from mcol1_external_data
        
        Returns:
            ComputeDataCreate ready for persistence
        """
        logger.info(f"Computing KOLMO metrics for {external_data.date}")
        
        # Step 1: Transform rates to KOLMO notation
        rates = self.transformer.transform(
            eur_usd=external_data.eur_usd,
            eur_cny=external_data.eur_cny
        )
        logger.debug(
            f"Transformed rates: ME4U={rates.r_me4u}, "
            f"IOU2={rates.r_iou2}, UOME={rates.r_uome}"
        )
        
        # Step 2: Compute KOLMO invariant (exact decimal)
        kolmo_value = self.calculator.compute_kolmo_value(
            rates.r_me4u, rates.r_iou2, rates.r_uome
        )
        kolmo_deviation = self.calculator.compute_deviation(kolmo_value)
        kolmo_state = self.calculator.compute_state(kolmo_value)
        logger.debug(
            f"KOLMO: value={kolmo_value}, deviation={kolmo_deviation}, "
            f"state={kolmo_state}"
        )
        
        # Step 3: Compute distances
        dist_me4u, dist_iou2, dist_uome = self.calculator.compute_distances(rates)
        logger.debug(
            f"Distances: ME4U={dist_me4u}, IOU2={dist_iou2}, UOME={dist_uome}"
        )
        
        # Step 4: Get previous day's distances for RelativePath
        prev_distances = await self._get_previous_distances(external_data.date)
        
        # Step 5: Compute RelativePaths
        relpath_me4u, relpath_iou2, relpath_uome = \
            self.calculator.compute_all_relativepaths(
                dist_me4u, dist_iou2, dist_uome,
                prev_distances.get("dist_me4u"),
                prev_distances.get("dist_iou2"),
                prev_distances.get("dist_uome")
            )
        logger.debug(
            f"RelativePaths: ME4U={relpath_me4u}, IOU2={relpath_iou2}, "
            f"UOME={relpath_uome}"
        )
        
        # Step 6: Select winner
        winner, winner_reason = self.winner_selector.select(
            relpath_me4u, relpath_iou2, relpath_uome
        )
        logger.info(
            f"Winner selected: {winner.value} "
            f"(rule: {winner_reason.selection_rule.value})"
        )
        
        # Build compute data
        return ComputeDataCreate(
            date=external_data.date,
            r_me4u=rates.r_me4u,
            r_iou2=rates.r_iou2,
            r_uome=rates.r_uome,
            kolmo_value=kolmo_value,
            kolmo_deviation=kolmo_deviation,
            kolmo_state=kolmo_state,
            dist_me4u=dist_me4u,
            dist_iou2=dist_iou2,
            dist_uome=dist_uome,
            relpath_me4u=relpath_me4u,
            relpath_iou2=relpath_iou2,
            relpath_uome=relpath_uome,
            winner=winner,
            winner_reason=winner_reason,
            mcol1_snapshot_id=external_data.mcol1_snapshot_id,
            mcol1_snapshot_compute_id=uuid4(),
            trace_compute_id=uuid4()
        )
    
    async def _get_previous_distances(
        self,
        current_date: date_type
    ) -> dict[str, Decimal | None]:
        """
        🔒 REQ-5.6: Fetch previous day's distances from database.
        """
        try:
            async with get_connection() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT dist_me4u, dist_iou2, dist_uome
                    FROM mcol1_compute_data
                    WHERE date = (
                        SELECT MAX(date) 
                        FROM mcol1_compute_data 
                        WHERE date < $1
                    )
                    """,
                    current_date
                )
                
                if row:
                    return {
                        "dist_me4u": Decimal(str(row["dist_me4u"])),
                        "dist_iou2": Decimal(str(row["dist_iou2"])),
                        "dist_uome": Decimal(str(row["dist_uome"]))
                    }
        except Exception as e:
            logger.warning(f"Could not fetch previous distances: {e}")
        
        return {
            "dist_me4u": None,
            "dist_iou2": None,
            "dist_uome": None
        }


async def persist_external_data(data: ExternalDataCreate) -> None:
    """
    🔒 REQ-1.2: Store raw provider data BEFORE computation.
    """
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO mcol1_external_data (
                date, eur_usd, eur_usd_pair_desc,
                eur_cny, eur_cny_pair_desc,
                eur_rub, eur_rub_pair_desc,
                eur_inr, eur_inr_pair_desc,
                eur_aed, eur_aed_pair_desc,
                mcol1_snapshot_id, trace_id, sources
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14
            )
            ON CONFLICT (date) DO UPDATE SET
                eur_usd = EXCLUDED.eur_usd,
                eur_cny = EXCLUDED.eur_cny,
                eur_rub = EXCLUDED.eur_rub,
                eur_inr = EXCLUDED.eur_inr,
                eur_aed = EXCLUDED.eur_aed,
                sources = EXCLUDED.sources,
                updated_at = NOW()
            """,
            data.date,
            data.eur_usd,
            data.eur_usd_pair_desc.value if data.eur_usd_pair_desc else None,
            data.eur_cny,
            data.eur_cny_pair_desc.value if data.eur_cny_pair_desc else None,
            data.eur_rub,
            data.eur_rub_pair_desc.value if data.eur_rub_pair_desc else None,
            data.eur_inr,
            data.eur_inr_pair_desc.value if data.eur_inr_pair_desc else None,
            data.eur_aed,
            data.eur_aed_pair_desc.value if data.eur_aed_pair_desc else None,
            data.mcol1_snapshot_id,
            data.trace_id,
            data.sources
        )
    logger.info(f"Persisted external data for {data.date}")


async def persist_compute_data(data: ComputeDataCreate) -> None:
    """
    🔒 REQ-1.3: Store computed KOLMO metrics.
    """
    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO mcol1_compute_data (
                date, r_me4u, r_iou2, r_uome,
                kolmo_value, kolmo_deviation, kolmo_state,
                dist_me4u, dist_iou2, dist_uome,
                relpath_me4u, relpath_iou2, relpath_uome,
                winner, winner_reason,
                mcol1_snapshot_id, mcol1_snapshot_compute_id, trace_compute_id
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 
                $11, $12, $13, $14, $15, $16, $17, $18
            )
            ON CONFLICT (date) DO UPDATE SET
                r_me4u = EXCLUDED.r_me4u,
                r_iou2 = EXCLUDED.r_iou2,
                r_uome = EXCLUDED.r_uome,
                kolmo_value = EXCLUDED.kolmo_value,
                kolmo_deviation = EXCLUDED.kolmo_deviation,
                kolmo_state = EXCLUDED.kolmo_state,
                dist_me4u = EXCLUDED.dist_me4u,
                dist_iou2 = EXCLUDED.dist_iou2,
                dist_uome = EXCLUDED.dist_uome,
                relpath_me4u = EXCLUDED.relpath_me4u,
                relpath_iou2 = EXCLUDED.relpath_iou2,
                relpath_uome = EXCLUDED.relpath_uome,
                winner = EXCLUDED.winner,
                winner_reason = EXCLUDED.winner_reason,
                updated_at = NOW()
            """,
            data.date,
            data.r_me4u,
            data.r_iou2,
            data.r_uome,
            data.kolmo_value,
            data.kolmo_deviation,
            data.kolmo_state.value,
            data.dist_me4u,
            data.dist_iou2,
            data.dist_uome,
            data.relpath_me4u,
            data.relpath_iou2,
            data.relpath_uome,
            data.winner.value,
            data.winner_reason.model_dump_json(),
            data.mcol1_snapshot_id,
            data.mcol1_snapshot_compute_id,
            data.trace_compute_id
        )
    logger.info(f"Persisted compute data for {data.date}: winner={data.winner.value}")
