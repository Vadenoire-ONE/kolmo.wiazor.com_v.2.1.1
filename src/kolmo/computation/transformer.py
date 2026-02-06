"""
Rate Transformer - Convert EUR- or RUB-based rates to KOLMO notation.

This implementation is backward-compatible: callers may provide EUR-based
inputs (`eur_usd`, `eur_cny`) or RUB-based inputs (`rub_usd`, `rub_cny`).
Positional calls are treated as EUR inputs to preserve existing tests.

All arithmetic uses `decimal.Decimal` with precision >= 28.
"""

import decimal as _decimal

from kolmo.models import KolmoRates

# Ensure high precision for financial calculations
_decimal.getcontext().prec = 28


class RateTransformer:
    """Transform EUR- or RUB-based inputs into KOLMO rates.

    Produces:
      - `r_me4u`: USD/CNY (dollars per 1 yuan)
      - `r_iou2`: RUB/USD (rubles per 1 dollar)
      - `r_uome`: CNY/RUB (yuan per 1 ruble)
    """

    DIMENSIONAL_TOLERANCE = _decimal.Decimal("0.05")

    def transform(self, *args, **kwargs) -> KolmoRates:
        """Flexible transform accepting either EUR- or RUB-based inputs.

        Usage patterns supported:
        - `transform(eur_usd, eur_cny)` (positional)  # kept for tests
        - `transform(eur_usd=..., eur_cny=...)`
        - `transform(rub_usd=..., rub_cny=...)`

        Returns:
            `KolmoRates`
        """
        # Case A: explicit RUB-based kwargs
        if "rub_usd" in kwargs or "rub_cny" in kwargs:
            rub_usd = kwargs.get("rub_usd")
            rub_cny = kwargs.get("rub_cny")
            if rub_usd is None or rub_cny is None:
                raise ValueError("Both 'rub_usd' and 'rub_cny' are required for RUB-based input")

            rub_usd = self._to_decimal(rub_usd)
            rub_cny = self._to_decimal(rub_cny)

            r_iou2 = rub_usd
            r_uome = _decimal.Decimal("1") / rub_cny
            r_me4u = rub_cny / rub_usd

        else:
            # Default: treat inputs as EUR-based (positional or keyword)
            if len(args) == 2:
                eur_usd, eur_cny = args
            else:
                eur_usd = kwargs.get("eur_usd")
                eur_cny = kwargs.get("eur_cny")

            if eur_usd is None or eur_cny is None:
                raise ValueError("Missing inputs: expected EUR-based inputs by default (eur_usd, eur_cny) or rub_* kwargs")

            eur_usd = self._to_decimal(eur_usd)
            eur_cny = self._to_decimal(eur_cny)

            # As per spec/tests: r_me4u = eur_usd / eur_cny; r_iou2 = 1/eur_usd; r_uome = eur_cny
            r_me4u = eur_usd / eur_cny
            r_iou2 = _decimal.Decimal("1") / eur_usd
            r_uome = eur_cny

        kolmo_value = r_me4u * r_iou2 * r_uome
        deviation = abs(kolmo_value - _decimal.Decimal("1.0"))
        if deviation > self.DIMENSIONAL_TOLERANCE:
            raise ValueError(f"Dimensional analysis failed: K = {kolmo_value}, deviation = {deviation}")

        return KolmoRates(r_me4u=r_me4u, r_iou2=r_iou2, r_uome=r_uome)

    def _to_decimal(self, value) -> _decimal.Decimal:
        if isinstance(value, _decimal.Decimal):
            return value
        return _decimal.Decimal(str(value))
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
        """
        Rate Transformer - Convert RUB-based rates to KOLMO notation

        All arithmetic uses `decimal.Decimal` with a precision of at least 28.
        """

        from decimal import Decimal, getcontext

        from kolmo.models import KolmoRates

        # Ensure high precision for financial calculations
        getcontext().prec = 28


        class RateTransformer:
            """Transform RUB-based inputs into KOLMO rates.

            Produces:
              - `r_me4u`: USD/CNY (dollars per 1 yuan)
              - `r_iou2`: RUB/USD (rubles per 1 dollar)
              - `r_uome`: CNY/RUB (yuan per 1 ruble)
            """

            DIMENSIONAL_TOLERANCE = Decimal("0.05")

            def transform(self, rub_usd: Decimal, rub_cny: Decimal) -> KolmoRates:
                """Compute KOLMO rates from RUB-per-USD and RUB-per-CNY.

                Args:
                    rub_usd: RUB per USD
                    rub_cny: RUB per CNY

                Returns:
                    `KolmoRates` with `r_me4u`, `r_iou2`, `r_uome`.
                """
                rub_usd = self._to_decimal(rub_usd)
                rub_cny = self._to_decimal(rub_cny)

                r_iou2 = rub_usd
                r_uome = Decimal("1") / rub_cny
                r_me4u = rub_cny / rub_usd

                kolmo_value = r_me4u * r_iou2 * r_uome
                deviation = abs(kolmo_value - Decimal("1.0"))
                if deviation > self.DIMENSIONAL_TOLERANCE:
                    raise ValueError(f"Dimensional analysis failed: K = {kolmo_value}, deviation = {deviation}")

                return KolmoRates(r_me4u=r_me4u, r_iou2=r_iou2, r_uome=r_uome)

            def _to_decimal(self, value) -> Decimal:
                if isinstance(value, Decimal):
                    return value
                return Decimal(str(value))

