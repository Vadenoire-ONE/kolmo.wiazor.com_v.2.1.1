#!/usr/bin/env python3
"""
Тесты для KOLMO Kalculator.

Покрытие:
  • Нормализация CBR (номиналы)
  • Winner↔Winner коэффициенты (инвариант: A_B × B_A = 1)
  • Fiat→Winner / Winner→Fiat (взаимная обратность)
  • RUB↔Winner через CBR-pivot
  • CBR↔Winner для произвольной валюты
  • Конкретные даты: 2026-01-29 (из kolmo_history.json)
"""

import json
import sys
from decimal import Decimal, getcontext
from pathlib import Path

import pytest

# Decimal precision, как в kalculator.py
getcontext().prec = 28

# Подключаем kalculator.py из scripts/
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import kalculator as kal  # noqa: E402

ONE = Decimal("1")


# ═══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _dec(s: str) -> Decimal:
    return Decimal(s)


def assert_close(a: Decimal, b: Decimal, tol: str = "1E-15") -> None:
    """Проверка приближённого равенства Decimal."""
    assert abs(a - b) < Decimal(tol), f"{a} ≠ {b} (±{tol})"


# ═══════════════════════════════════════════════════════════════════════════════
#  Fixture: тестовые KOLMO-ставки (дата 2026-01-29)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def rates_20260129():
    """KOLMO-ставки за 2026-01-29 из kolmo_history.json."""
    return {
        "r_me4u": _dec("0.143964"),
        "r_iou2": _dec("0.835561"),
        "r_uome": _dec("8.313200"),
        "winner": "IOU2",
    }


@pytest.fixture
def cbr_sample():
    """Примерные CBR-курсы (RUB за 1 единицу, условные)."""
    return {
        "USD": _dec("92.5000"),
        "EUR": _dec("100.5000"),
        "CNY": _dec("12.8000"),
        "GBP": _dec("116.0000"),
        "JPY": _dec("0.6100"),      # уже нормализованный (за 1 JPY)
        "CHF": _dec("105.0000"),
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  Test: Decimal helpers
# ═══════════════════════════════════════════════════════════════════════════════

class TestDecimalHelpers:

    def test_d_from_str(self):
        assert kal._d("0.143964") == _dec("0.143964")

    def test_d_from_decimal(self):
        d = _dec("1.23456")
        assert kal._d(d) is d  # identity

    def test_serialize_no_exponent(self):
        d = _dec("6.788634127999999102E-5")
        s = kal._serialize(d)
        assert "E" not in s and "e" not in s

    def test_serialize_18_decimals(self):
        d = _dec("0.143964")
        s = kal._serialize(d)
        # Должно быть ровно 18 знаков после точки
        integer_part, frac_part = s.split(".")
        assert len(frac_part) == 18


# ═══════════════════════════════════════════════════════════════════════════════
#  Test: Winner ↔ Winner
# ═══════════════════════════════════════════════════════════════════════════════

class TestWinnerToWinner:

    def test_inverse_pairs(self, rates_20260129):
        r = rates_20260129
        w2w = kal.compute_winner_to_winner(r["r_me4u"], r["r_iou2"], r["r_uome"])

        # ME4U_IOU2 × IOU2_ME4U = 1
        assert_close(w2w["ME4U_IOU2"] * w2w["IOU2_ME4U"], ONE)
        # ME4U_UOME × UOME_ME4U = 1
        assert_close(w2w["ME4U_UOME"] * w2w["UOME_ME4U"], ONE)
        # IOU2_UOME × UOME_IOU2 = 1
        assert_close(w2w["IOU2_UOME"] * w2w["UOME_IOU2"], ONE)

    def test_me4u_iou2_value(self, rates_20260129):
        """ME4U→IOU2 = r_me4u (1 CNY → r_me4u USD)."""
        r = rates_20260129
        w2w = kal.compute_winner_to_winner(r["r_me4u"], r["r_iou2"], r["r_uome"])
        assert w2w["ME4U_IOU2"] == r["r_me4u"]

    def test_iou2_uome_value(self, rates_20260129):
        """IOU2→UOME = r_iou2 (1 USD → r_iou2 EUR)."""
        r = rates_20260129
        w2w = kal.compute_winner_to_winner(r["r_me4u"], r["r_iou2"], r["r_uome"])
        assert w2w["IOU2_UOME"] == r["r_iou2"]

    def test_triangle_consistency(self, rates_20260129):
        """ME4U→IOU2→UOME→ME4U ≈ 1 (по KOLMO-инварианту)."""
        r = rates_20260129
        w2w = kal.compute_winner_to_winner(r["r_me4u"], r["r_iou2"], r["r_uome"])
        cycle = w2w["ME4U_IOU2"] * w2w["IOU2_UOME"] * w2w["UOME_ME4U"]
        # Это = r_me4u × r_iou2 × r_uome = KOLMO invariant ≈ 1
        assert_close(cycle, ONE, tol="0.001")


# ═══════════════════════════════════════════════════════════════════════════════
#  Test: Fiat → Winner / Winner → Fiat
# ═══════════════════════════════════════════════════════════════════════════════

class TestFiatWinner:

    def test_fiat_winner_inverse(self, rates_20260129):
        """fiat_to_winner[X_COIN] × winner_to_fiat[COIN_X] = 1."""
        r = rates_20260129
        f2w = kal.compute_fiat_to_winner(r["r_me4u"], r["r_iou2"], r["r_uome"])
        w2f = kal.compute_winner_to_fiat(r["r_me4u"], r["r_iou2"], r["r_uome"])

        pairs = [
            ("CNY_ME4U", "ME4U_CNY"),
            ("USD_ME4U", "ME4U_USD"),
            ("EUR_ME4U", "ME4U_EUR"),
            ("USD_IOU2", "IOU2_USD"),
            ("EUR_IOU2", "IOU2_EUR"),
            ("CNY_IOU2", "IOU2_CNY"),
            ("EUR_UOME", "UOME_EUR"),
            ("USD_UOME", "UOME_USD"),
            ("CNY_UOME", "UOME_CNY"),
        ]
        for fk, wk in pairs:
            assert_close(f2w[fk] * w2f[wk], ONE, tol="1E-15")

    def test_identity_coefficients(self, rates_20260129):
        """Тождественные коэффициенты = 1 для базовых пар."""
        r = rates_20260129
        f2w = kal.compute_fiat_to_winner(r["r_me4u"], r["r_iou2"], r["r_uome"])
        assert f2w["CNY_ME4U"] == ONE
        assert f2w["USD_IOU2"] == ONE
        assert f2w["EUR_UOME"] == ONE

    def test_usd_me4u_formula(self, rates_20260129):
        """USD→ME4U = 1/r_me4u (spec formula)."""
        r = rates_20260129
        f2w = kal.compute_fiat_to_winner(r["r_me4u"], r["r_iou2"], r["r_uome"])
        expected = ONE / r["r_me4u"]
        assert_close(f2w["USD_ME4U"], expected)

    def test_eur_me4u_formula(self, rates_20260129):
        """EUR→ME4U = r_uome (spec formula: 1 EUR = r_uome CNY = r_uome ME4U)."""
        r = rates_20260129
        f2w = kal.compute_fiat_to_winner(r["r_me4u"], r["r_iou2"], r["r_uome"])
        assert f2w["EUR_ME4U"] == r["r_uome"]


# ═══════════════════════════════════════════════════════════════════════════════
#  Test: RUB ↔ Winner
# ═══════════════════════════════════════════════════════════════════════════════

class TestRubWinner:

    def test_rub_winner_inverse(self, rates_20260129, cbr_sample):
        r = rates_20260129
        blocks = kal.compute_rub_winner(
            r["r_me4u"], r["r_iou2"], r["r_uome"],
            cbr_sample["USD"], cbr_sample["EUR"], cbr_sample["CNY"],
        )
        r2w = blocks["rub_to_winner"]
        w2r = blocks["winner_to_rub"]
        # RUB_ME4U × ME4U_RUB = 1
        assert_close(r2w["RUB_ME4U"] * w2r["ME4U_RUB"], ONE)
        assert_close(r2w["RUB_IOU2"] * w2r["IOU2_RUB"], ONE)
        assert_close(r2w["RUB_UOME"] * w2r["UOME_RUB"], ONE)

    def test_rub_me4u_value(self, rates_20260129, cbr_sample):
        r = rates_20260129
        blocks = kal.compute_rub_winner(
            r["r_me4u"], r["r_iou2"], r["r_uome"],
            cbr_sample["USD"], cbr_sample["EUR"], cbr_sample["CNY"],
        )
        # RUB→ME4U = 1/cbr_cny  (1 RUB → 1/12.8000 CNY = 1/12.8 ME4U)
        expected = ONE / cbr_sample["CNY"]
        assert_close(blocks["rub_to_winner"]["RUB_ME4U"], expected)


# ═══════════════════════════════════════════════════════════════════════════════
#  Test: CBR ↔ Winner
# ═══════════════════════════════════════════════════════════════════════════════

class TestCbrWinner:

    def test_cbr_winner_inverse(self, cbr_sample):
        """X_WINNER × WINNER_X = 1 для каждого X."""
        blocks = kal.compute_cbr_to_winner("IOU2", cbr_sample)
        c2w = blocks["cbr_to_winner"]
        w2c = blocks["winner_to_cbr"]
        for code in cbr_sample:
            key_to = f"{code}_IOU2"
            key_from = f"IOU2_{code}"
            if key_to in c2w and key_from in w2c:
                assert_close(c2w[key_to] * w2c[key_from], ONE)

    def test_usd_iou2_identity(self, cbr_sample):
        """USD→IOU2 через CBR-pivot = cbr_usd/cbr_usd = 1."""
        blocks = kal.compute_cbr_to_winner("IOU2", cbr_sample)
        assert_close(blocks["cbr_to_winner"]["USD_IOU2"], ONE)

    def test_gbp_iou2_formula(self, cbr_sample):
        """GBP→IOU2 = cbr_gbp / cbr_usd."""
        blocks = kal.compute_cbr_to_winner("IOU2", cbr_sample)
        expected = cbr_sample["GBP"] / cbr_sample["USD"]
        assert_close(blocks["cbr_to_winner"]["GBP_IOU2"], expected)


# ═══════════════════════════════════════════════════════════════════════════════
#  Test: compute_day — интеграция
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputeDay:

    def test_all_blocks_present(self, rates_20260129, cbr_sample):
        result = kal.compute_day("2026-01-29", rates_20260129, cbr_sample)
        expected_keys = {
            "date", "winner", "r_me4u", "r_iou2", "r_uome",
            "winner_to_winner", "fiat_to_winner", "winner_to_fiat",
            "rub_to_winner", "winner_to_rub",
            "cbr_to_winner", "winner_to_cbr",
        }
        assert expected_keys == set(result.keys())

    def test_winner_matches(self, rates_20260129, cbr_sample):
        result = kal.compute_day("2026-01-29", rates_20260129, cbr_sample)
        assert result["winner"] == "IOU2"

    def test_no_cbr_graceful(self, rates_20260129):
        """Без CBR-данных блоки RUB/CBR пустые, но не ошибка."""
        result = kal.compute_day("2026-01-29", rates_20260129, None)
        assert result["rub_to_winner"] == {}
        assert result["winner_to_rub"] == {}
        assert result["cbr_to_winner"] == {}
        assert result["winner_to_cbr"] == {}

    def test_serialization_no_float(self, rates_20260129, cbr_sample):
        """Все числовые значения в JSON — строки, не float."""
        result = kal.compute_day("2026-01-29", rates_20260129, cbr_sample)
        # Проверяем фиксированные поля
        assert isinstance(result["r_me4u"], str)
        assert isinstance(result["r_iou2"], str)
        # Проверяем вложенные блоки
        for key in ("winner_to_winner", "fiat_to_winner", "rub_to_winner"):
            for v in result[key].values():
                assert isinstance(v, str), f"{key}: значение {v!r} не строка"


# ═══════════════════════════════════════════════════════════════════════════════
#  Test: CBR номиналы
# ═══════════════════════════════════════════════════════════════════════════════

class TestCbrNominals:

    def test_known_nominals(self):
        noms = kal._cbr_nominals()
        assert noms["JPY"] == 100
        assert noms["KRW"] == 1000
        assert noms["USD"] == 1
        assert noms["EUR"] == 1
        assert noms["AMD"] == 100

    def test_normalization(self):
        """Проверяем, что 6584 (raw за 100 JPY) → 65.84 за 1 JPY."""
        noms = kal._cbr_nominals()
        raw_jpy = _dec("65.8309")  # из cbr_of_rub.json за 2021-07-01
        normalized = raw_jpy / Decimal(str(noms["JPY"]))
        assert_close(normalized, _dec("0.658309"))


# ═══════════════════════════════════════════════════════════════════════════════
#  Test: ручной расчёт для 2026-01-29
# ═══════════════════════════════════════════════════════════════════════════════

class TestGoldenDate20260129:
    """Сверка с ручным расчётом по формулам из спецификации."""

    def test_me4u_iou2(self, rates_20260129):
        """ME4U→IOU2 = r_me4u = 0.143964."""
        r = rates_20260129
        w2w = kal.compute_winner_to_winner(r["r_me4u"], r["r_iou2"], r["r_uome"])
        assert_close(w2w["ME4U_IOU2"], _dec("0.143964"))

    def test_iou2_uome(self, rates_20260129):
        """IOU2→UOME = r_iou2 = 0.835561."""
        r = rates_20260129
        w2w = kal.compute_winner_to_winner(r["r_me4u"], r["r_iou2"], r["r_uome"])
        assert_close(w2w["IOU2_UOME"], _dec("0.835561"))

    def test_usd_me4u(self, rates_20260129):
        """USD→ME4U = 1/r_me4u = 1/0.143964 ≈ 6.94618…."""
        r = rates_20260129
        f2w = kal.compute_fiat_to_winner(r["r_me4u"], r["r_iou2"], r["r_uome"])
        expected = ONE / _dec("0.143964")
        assert_close(f2w["USD_ME4U"], expected)

    def test_eur_me4u(self, rates_20260129):
        """EUR→ME4U = r_uome = 8.313200."""
        r = rates_20260129
        f2w = kal.compute_fiat_to_winner(r["r_me4u"], r["r_iou2"], r["r_uome"])
        assert_close(f2w["EUR_ME4U"], _dec("8.313200"))

    def test_kolmo_invariant(self, rates_20260129):
        """r_me4u × r_iou2 × r_uome ≈ 1."""
        r = rates_20260129
        k = r["r_me4u"] * r["r_iou2"] * r["r_uome"]
        assert_close(k, ONE, tol="0.001")
