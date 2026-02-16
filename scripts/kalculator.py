#!/usr/bin/env python3
"""
KOLMO Kalculator — вычисление коэффициентов конверсии winner-коинов / фиат / CBR-валют.

Модуль загружает:
  • kolmo_history.json  — KOLMO-курсы r_me4u, r_iou2, r_uome и winner
  • cbr_of_rub.json     — нормализованные курсы ЦБ РФ (ratetorub по nominal=1, но
                          для некоторых валют CBR отдаёт номинал > 1 — мы здесь
                          оперируем уже «приведёнными» значениями, где nominal учтён
                          при экспорте)

Вычисляет на каждую дату:
  • winner_to_winner  — 6 коэффициентов ME4U↔IOU2↔UOME
  • fiat_to_winner    — USD/EUR/CNY → каждый winner-коин
  • winner_to_fiat    — каждый winner-коин → USD/EUR/CNY
  • rub_to_winner     — RUB → ME4U / IOU2 / UOME
  • winner_to_rub     — ME4U / IOU2 / UOME → RUB
  • cbr_to_winner     — все CBR-валюты → winner (через RUB-pivot)
  • winner_to_cbr     — winner → все CBR-валюты (через RUB-pivot)

Результат сохраняется в conversion_coefficients.json.

Допущения DTKT M0.1:
  1 ME4U ≡ 1 CNY
  1 IOU2 ≡ 1 USD
  1 UOME ≡ 1 EUR

Ссылки:
  KOLMO.wiazor.com Technical Specification v.2.1.1  §2.1, §5
  KOLMO Kalculator Module Technical Specification

Использование:
  python scripts/kalculator.py                # полный пересчёт за весь период
  python scripts/kalculator.py --date 2026-01-29   # один день
  python scripts/kalculator.py --start 2025-01-01 --end 2025-12-31
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime
from decimal import Decimal, getcontext, ROUND_HALF_EVEN, InvalidOperation
from pathlib import Path
from typing import Any

# ─── Decimal context ──────────────────────────────────────────────────────────
# 🔒 REQ-5.3: precision ≥ 28
getcontext().prec = 28
getcontext().rounding = ROUND_HALF_EVEN

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("kalculator")

# ─── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_EXPORT_DIR = SCRIPT_DIR.parent / "data" / "export"
KOLMO_HISTORY_FILE = DATA_EXPORT_DIR / "kolmo_history.json"
CBR_RUB_FILE = DATA_EXPORT_DIR / "cbr_of_rub.json"
OUTPUT_FILE = DATA_EXPORT_DIR / "conversion_coefficients.json"

# ─── Constants ────────────────────────────────────────────────────────────────
ONE = Decimal("1")
ZERO = Decimal("0")
# Базовые валюты для каждого коина (DTKT M0.1)
COIN_BASE: dict[str, str] = {
    "ME4U": "CNY",
    "IOU2": "USD",
    "UOME": "EUR",
}
# Валюты, которые НЕ являются отдельными CBR-кодами (они уже входят в fiat-блок)
FIAT_CODES = {"USD", "EUR", "CNY"}


# ═══════════════════════════════════════════════════════════════════════════════
#  Decimal helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _d(value: str | float | int | Decimal) -> Decimal:
    """Безопасное преобразование в Decimal, никогда через float промежуточно."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _serialize(d: Decimal) -> str:
    """
    Сериализация Decimal → str для JSON.
    Фиксированная точечная запись, до 18 знаков после точки.
    Без научной нотации (E).
    """
    # quantize к 18 знакам
    try:
        quantized = d.quantize(Decimal("1E-18"), rounding=ROUND_HALF_EVEN)
    except InvalidOperation:
        # Если число слишком велико для квантования к 18 знакам —
        # вернём нормализованную строку
        quantized = d.normalize()
    # Гарантируем отсутствие 'E' в выводе
    result = format(quantized, "f")
    return result


# ═══════════════════════════════════════════════════════════════════════════════
#  Data loaders
# ═══════════════════════════════════════════════════════════════════════════════

def load_kolmo_history(path: Path = KOLMO_HISTORY_FILE) -> dict[str, dict[str, Any]]:
    """
    Загружает kolmo_history.json → dict[date_str → record].

    Returns:
        Словарь {date: {r_me4u, r_iou2, r_uome, winner}} с Decimal-значениями.
    """
    logger.info("Загрузка KOLMO-истории из %s", path)
    with open(path, "r", encoding="utf-8") as f:
        raw: list[dict] = json.load(f)

    result: dict[str, dict[str, Any]] = {}
    for rec in raw:
        dt = rec["date"]
        try:
            result[dt] = {
                "r_me4u": _d(rec["r_me4u"]),
                "r_iou2": _d(rec["r_iou2"]),
                "r_uome": _d(rec["r_uome"]),
                "winner": rec["winner"],
            }
        except (KeyError, InvalidOperation) as exc:
            logger.warning("Пропущена запись KOLMO %s: %s", dt, exc)
    logger.info("KOLMO: загружено %d дат", len(result))
    return result


def load_cbr_data(path: Path = CBR_RUB_FILE) -> dict[str, dict[str, Decimal]]:
    """
    Загружает cbr_of_rub.json → dict[date_str → {code: RUB_per_1_unit}].

    В файле CBR значения уже приведены к nominal=1 (__export_cbr_rub.py__
    записывает ratetorub с учётом nominal): для валют с nominal>1 (JPY, AMD…)
    значение уже пересчитано при экспорте.

    Однако если файл содержит «сырые» котировки CBR (100 JPY = … RUB),
    то значение для JPY уже «за nominal» единиц.  Поскольку в нашем файле
    поля `nominal` нет, мы принимаем, что оператор уже нормализовал данные.

    Returns:
        {date: {currency_code: Decimal(RUB per 1 unit)}}
    """
    logger.info("Загрузка CBR-данных из %s", path)
    with open(path, "r", encoding="utf-8") as f:
        raw: list[dict] = json.load(f)

    # Определяем, есть ли в данных номиналы.
    # В текущем формате cbr_of_rub.json — плоская структура без nominal:
    # {"date": "...", "USD": "72.7234", "EUR": "86.5118", ...}
    # Значения — ratetorub-за-nominal, где nominal задан CBR.
    # Нам нужно привести к «за 1 единицу».
    # CBR номиналы (зафиксированы):
    CBR_NOMINALS: dict[str, int] = _cbr_nominals()

    result: dict[str, dict[str, Decimal]] = {}
    for rec in raw:
        dt = rec["date"]
        currencies: dict[str, Decimal] = {}
        for code, val in rec.items():
            if code == "date":
                continue
            try:
                rate_raw = _d(val)
                nominal = CBR_NOMINALS.get(code, 1)
                # r_rub[code] = ratetorub / nominal  → RUB за 1 единицу
                currencies[code] = rate_raw / Decimal(str(nominal))
            except (InvalidOperation, TypeError) as exc:
                logger.debug("CBR: пропуск %s/%s: %s", dt, code, exc)
        result[dt] = currencies

    logger.info("CBR: загружено %d дат", len(result))
    return result


def _cbr_nominals() -> dict[str, int]:
    """
    Номиналы CBR: количество единиц валюты в одной котировке.
    Для большинства валют nominal=1; исключения перечислены ниже.
    Источник: https://cbr.ru/scripts/XML_daily.asp (поле <Nominal>).

    ВАЖНО: если в cbr_of_rub.json данные уже нормализованы (ratetorub / nominal),
    все номиналы считаются равными 1.  Эта таблица применяется только тогда,
    когда данные «сырые» (ratetorub за nominal единиц).
    """
    return {
        # Номиналы, отличные от 1 (по состоянию ЦБ РФ на 2025)
        "AMD": 100,
        "BYN": 1,  # ранее 10000 (до деноминации)
        "HUF": 100,
        "HKD": 10,
        "DKK": 10,
        "INR": 100,
        "KZT": 100,
        "KGS": 100,
        "CNY": 1,
        "MDL": 10,
        "NOK": 10,
        "PLN": 10,
        "RON": 10,
        "XDR": 1,
        "SGD": 1,
        "TJS": 10,
        "TRY": 10,
        "TMT": 1,
        "UZS": 10000,
        "UAH": 10,
        "CZK": 10,
        "SEK": 10,
        "ZAR": 10,
        "KRW": 1000,
        "JPY": 100,

        # Номинал = 1 (записывать не обязательно, но для полноты)
        "AUD": 1,
        "AZN": 1,
        "GBP": 1,
        "BGN": 1,
        "BRL": 1,
        "USD": 1,
        "EUR": 1,
        "CAD": 1,
        "CHF": 1,

        # Дополнительные (добавлены позже CBR)
        "AED": 1,
        "EGP": 10,
        "IDR": 10000,
        "IRR": 100000,
        "QAR": 1,
        "CUP": 1,
        "MNT": 100,
        "NGN": 100,
        "NZD": 1,
        "OMR": 1,
        "SAR": 1,
        "BDT": 100,
        "THB": 10,
        "ETB": 100,
        "RSD": 100,
        "MMK": 1000,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  Core computation
# ═══════════════════════════════════════════════════════════════════════════════

def compute_winner_to_winner(
    r_me4u: Decimal,
    r_iou2: Decimal,
    r_uome: Decimal,
) -> dict[str, Decimal]:
    """
    Winner↔Winner коэффициенты (6 пар).

    Формулы основаны на DTKT M0.1:
      ME4U≡CNY, IOU2≡USD, UOME≡EUR.
      r_me4u = USD/CNY; r_iou2 = EUR/USD; r_uome = CNY/EUR.

    Чтобы конвертировать 1 ME4U (= 1 CNY) в IOU2 (= 1 USD),
    нужно узнать, сколько USD стоит 1 CNY → это r_me4u (USD/CNY).
    Но r_me4u ≈ 0.14 — столько USD за 1 CNY.
    Однако по определению «ME4U_IOU2 = сколько IOU2 получишь за 1 ME4U»:
      1 ME4U = 1 CNY → (1 CNY) × (r_me4u USD/CNY) = r_me4u USD = r_me4u IOU2.

    Проверка: ME4U_IOU2 × IOU2_ME4U = 1 ✓ (r_me4u × (1/r_me4u) = 1).
    """
    return {
        # ME4U → IOU2: 1 ME4U = 1 CNY, нужно получить IOU2(=USD).
        # CNY→USD = r_me4u (USD/CNY), значит 1 ME4U → r_me4u IOU2.
        "ME4U_IOU2": r_me4u,
        "IOU2_ME4U": ONE / r_me4u,

        # ME4U → UOME: 1 ME4U = 1 CNY → EUR.
        # CNY→EUR: мы знаем r_uome = CNY/EUR, т.е. 1 EUR = r_uome CNY.
        # Значит 1 CNY = 1/r_uome EUR = 1/r_uome UOME.
        "ME4U_UOME": ONE / r_uome,
        "UOME_ME4U": r_uome,

        # IOU2 → UOME: 1 IOU2 = 1 USD → EUR.
        # USD→EUR = r_iou2 (EUR/USD), т.е. 1 USD = r_iou2 EUR = r_iou2 UOME.
        "IOU2_UOME": r_iou2,
        "UOME_IOU2": ONE / r_iou2,
    }


def compute_fiat_to_winner(
    r_me4u: Decimal,
    r_iou2: Decimal,
    r_uome: Decimal,
) -> dict[str, Decimal]:
    """
    Fiat → Winner: сколько winner-коинов получишь за 1 единицу fiat (USD/EUR/CNY).

    ME4U (≡CNY):
      CNY → ME4U: 1 (тождество)
      USD → ME4U: 1 USD → ? CNY.  r_me4u = USD/CNY ≈ 0.14, значит
                  1 USD = 1/r_me4u CNY = 1/r_me4u ME4U.
      EUR → ME4U: 1 EUR = r_uome CNY = r_uome ME4U.

    IOU2 (≡USD):
      USD → IOU2: 1
      EUR → IOU2: 1 EUR → ? USD.  r_iou2 = EUR/USD, 1 EUR = 1/r_iou2 USD = 1/r_iou2 IOU2.
      CNY → IOU2: 1 CNY → ? USD.  r_me4u = USD/CNY, 1 CNY = r_me4u USD = r_me4u IOU2.

    UOME (≡EUR):
      EUR → UOME: 1
      USD → UOME: 1 USD → ? EUR.  r_iou2 = EUR/USD, 1 USD = r_iou2 EUR = r_iou2 UOME.
      CNY → UOME: 1 CNY → ? EUR.  r_uome = CNY/EUR, 1 CNY = 1/r_uome EUR = 1/r_uome UOME.
    """
    return {
        # — ME4U (base=CNY) —
        "CNY_ME4U": ONE,
        "USD_ME4U": ONE / r_me4u,
        "EUR_ME4U": r_uome,

        # — IOU2 (base=USD) —
        "USD_IOU2": ONE,
        "EUR_IOU2": ONE / r_iou2,
        "CNY_IOU2": r_me4u,

        # — UOME (base=EUR) —
        "EUR_UOME": ONE,
        "USD_UOME": r_iou2,
        "CNY_UOME": ONE / r_uome,
    }


def compute_winner_to_fiat(
    r_me4u: Decimal,
    r_iou2: Decimal,
    r_uome: Decimal,
) -> dict[str, Decimal]:
    """
    Winner → Fiat: обратные к fiat_to_winner.

    ME4U → CNY: 1
    ME4U → USD: r_me4u  (1 ME4U = 1 CNY = r_me4u USD)
    ME4U → EUR: 1/r_uome  (1 CNY = 1/r_uome EUR)

    IOU2 → USD: 1
    IOU2 → EUR: r_iou2  (1 USD = r_iou2 EUR)
    IOU2 → CNY: 1/r_me4u  (1 USD = 1/r_me4u CNY)

    UOME → EUR: 1
    UOME → USD: 1/r_iou2
    UOME → CNY: r_uome
    """
    return {
        # — ME4U → fiat —
        "ME4U_CNY": ONE,
        "ME4U_USD": r_me4u,
        "ME4U_EUR": ONE / r_uome,

        # — IOU2 → fiat —
        "IOU2_USD": ONE,
        "IOU2_EUR": r_iou2,
        "IOU2_CNY": ONE / r_me4u,

        # — UOME → fiat —
        "UOME_EUR": ONE,
        "UOME_USD": ONE / r_iou2,
        "UOME_CNY": r_uome,
    }


def compute_rub_winner(
    r_me4u: Decimal,
    r_iou2: Decimal,
    r_uome: Decimal,
    cbr_usd: Decimal,
    cbr_eur: Decimal,
    cbr_cny: Decimal,
) -> dict[str, dict[str, Decimal]]:
    """
    RUB ↔ Winner через CBR-pivot.

    r_rub[X] = RUB за 1 единицу X (уже нормализовано).

    RUB → ME4U: 1 RUB → CNY → ME4U.  1 RUB = 1/cbr_cny CNY = 1/cbr_cny ME4U.
    RUB → IOU2: 1 RUB = 1/cbr_usd USD = 1/cbr_usd IOU2.
    RUB → UOME: 1 RUB = 1/cbr_eur EUR = 1/cbr_eur UOME.
    """
    rub_to_winner = {
        "RUB_ME4U": ONE / cbr_cny,
        "RUB_IOU2": ONE / cbr_usd,
        "RUB_UOME": ONE / cbr_eur,
    }
    winner_to_rub = {
        "ME4U_RUB": cbr_cny,
        "IOU2_RUB": cbr_usd,
        "UOME_RUB": cbr_eur,
    }
    return {"rub_to_winner": rub_to_winner, "winner_to_rub": winner_to_rub}


def compute_cbr_to_winner(
    winner: str,
    cbr_rates: dict[str, Decimal],
) -> dict[str, dict[str, Decimal]]:
    """
    Любая CBR-валюта X ↔ winner-коин дня.

    Принцип: используем RUB как pivot.
    Базовая валюта winner-коина: b = COIN_BASE[winner].
    r_rub[b] = cbr_rates[b].

    X → winner: (r_rub[X] / r_rub[b])  единиц winner за 1 X.
    winner → X: (r_rub[b] / r_rub[X])  единиц X за 1 winner.

    Мы рассчитываем для ВСЕХ CBR-валют (исключая сам winner-base, чтобы
    не дублировать fiat_to_winner, но для полноты включаем).
    """
    base_code = COIN_BASE[winner]
    base_rub = cbr_rates.get(base_code)
    if base_rub is None or base_rub == ZERO:
        logger.warning("CBR: нет курса для %s, пропуск cbr_to_winner", base_code)
        return {"cbr_to_winner": {}, "winner_to_cbr": {}}

    cbr_to_win: dict[str, Decimal] = {}
    win_to_cbr: dict[str, Decimal] = {}

    for code, rate_rub in cbr_rates.items():
        if rate_rub is None or rate_rub == ZERO:
            continue
        key_to = f"{code}_{winner}"
        key_from = f"{winner}_{code}"
        cbr_to_win[key_to] = rate_rub / base_rub
        win_to_cbr[key_from] = base_rub / rate_rub

    return {"cbr_to_winner": cbr_to_win, "winner_to_cbr": win_to_cbr}


def compute_day(
    dt: str,
    kolmo: dict[str, Any],
    cbr_rates: dict[str, Decimal] | None,
) -> dict[str, Any]:
    """
    Вычисляет полный набор коэффициентов конверсии для одной даты.

    Args:
        dt: дата ISO 8601 (str).
        kolmo: {r_me4u, r_iou2, r_uome, winner} — Decimal.
        cbr_rates: {code: Decimal(RUB per 1 unit)} или None, если нет.

    Returns:
        Словарь со всеми блоками коэффициентов.
    """
    r_me4u = kolmo["r_me4u"]
    r_iou2 = kolmo["r_iou2"]
    r_uome = kolmo["r_uome"]
    winner = kolmo["winner"]

    day_result: dict[str, Any] = {
        "date": dt,
        "winner": winner,
        "r_me4u": _serialize(r_me4u),
        "r_iou2": _serialize(r_iou2),
        "r_uome": _serialize(r_uome),
    }

    # 1. Winner ↔ Winner
    w2w = compute_winner_to_winner(r_me4u, r_iou2, r_uome)
    day_result["winner_to_winner"] = {k: _serialize(v) for k, v in w2w.items()}

    # 2. Fiat → Winner
    f2w = compute_fiat_to_winner(r_me4u, r_iou2, r_uome)
    day_result["fiat_to_winner"] = {k: _serialize(v) for k, v in f2w.items()}

    # 3. Winner → Fiat
    w2f = compute_winner_to_fiat(r_me4u, r_iou2, r_uome)
    day_result["winner_to_fiat"] = {k: _serialize(v) for k, v in w2f.items()}

    # 4–5. RUB ↔ Winner  (только если есть CBR)
    if cbr_rates and all(
        cbr_rates.get(c) for c in ("USD", "EUR", "CNY")
    ):
        cbr_usd = cbr_rates["USD"]
        cbr_eur = cbr_rates["EUR"]
        cbr_cny = cbr_rates["CNY"]

        rub_blocks = compute_rub_winner(
            r_me4u, r_iou2, r_uome, cbr_usd, cbr_eur, cbr_cny,
        )
        day_result["rub_to_winner"] = {
            k: _serialize(v) for k, v in rub_blocks["rub_to_winner"].items()
        }
        day_result["winner_to_rub"] = {
            k: _serialize(v) for k, v in rub_blocks["winner_to_rub"].items()
        }

        # 6–7. CBR-валюты ↔ winner
        cbr_blocks = compute_cbr_to_winner(winner, cbr_rates)
        day_result["cbr_to_winner"] = {
            k: _serialize(v) for k, v in cbr_blocks["cbr_to_winner"].items()
        }
        day_result["winner_to_cbr"] = {
            k: _serialize(v) for k, v in cbr_blocks["winner_to_cbr"].items()
        }
    else:
        logger.debug("CBR: нет полных данных за %s, блоки RUB/CBR опущены", dt)
        day_result["rub_to_winner"] = {}
        day_result["winner_to_rub"] = {}
        day_result["cbr_to_winner"] = {}
        day_result["winner_to_cbr"] = {}

    return day_result


# ═══════════════════════════════════════════════════════════════════════════════
#  JSON encoder
# ═══════════════════════════════════════════════════════════════════════════════

class _DecimalAwareEncoder(json.JSONEncoder):
    """JSON-энкодер: Decimal → str (без float-промежутка)."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return _serialize(obj)
        if isinstance(obj, date):
            return obj.isoformat()
        return super().default(obj)


# ═══════════════════════════════════════════════════════════════════════════════
#  Main pipeline
# ═══════════════════════════════════════════════════════════════════════════════

def run(
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    single_date: str | None = None,
    output_path: Path = OUTPUT_FILE,
) -> Path:
    """
    Основной pipeline: загрузить данные → вычислить → сохранить.

    Args:
        start_date:  начало периода YYYY-MM-DD (по умолчанию — первая дата KOLMO).
        end_date:    конец периода YYYY-MM-DD  (по умолчанию — последняя дата KOLMO).
        single_date: если задан, обработать одну дату.
        output_path: путь для записи JSON.

    Returns:
        Path к записанному файлу.
    """
    # ── Загрузка ──────────────────────────────────────────────────────────
    kolmo_data = load_kolmo_history()
    cbr_data = load_cbr_data()

    # ── Определяем диапазон ───────────────────────────────────────────────
    all_kolmo_dates = sorted(kolmo_data.keys())
    if not all_kolmo_dates:
        raise RuntimeError("KOLMO-история пуста — нечего считать.")

    if single_date:
        target_dates = [single_date]
    else:
        first = start_date or all_kolmo_dates[0]
        last = end_date or all_kolmo_dates[-1]
        target_dates = [d for d in all_kolmo_dates if first <= d <= last]

    logger.info(
        "Расчёт коэффициентов: %d дат (%s — %s)",
        len(target_dates),
        target_dates[0] if target_dates else "?",
        target_dates[-1] if target_dates else "?",
    )

    # ── Стратегия fallback для CBR ────────────────────────────────────────
    # Если нет CBR за конкретную дату, берём ближайшую предыдущую.
    sorted_cbr_dates = sorted(cbr_data.keys())

    def _cbr_for_date(dt: str) -> dict[str, Decimal] | None:
        """Возвращает CBR-данные за дату или ближайший предшествующий рабочий день."""
        if dt in cbr_data:
            return cbr_data[dt]
        # fallback: предыдущий ближайший
        for cd in reversed(sorted_cbr_dates):
            if cd < dt:
                logger.debug("CBR fallback: %s → %s", dt, cd)
                return cbr_data[cd]
        return None

    # ── Расчёт ────────────────────────────────────────────────────────────
    results: dict[str, Any] = {}
    skipped = 0
    for dt in target_dates:
        kolmo = kolmo_data.get(dt)
        if kolmo is None:
            logger.warning("KOLMO: нет данных за %s — пропуск", dt)
            skipped += 1
            continue
        cbr = _cbr_for_date(dt)
        results[dt] = compute_day(dt, kolmo, cbr)

    logger.info(
        "Рассчитано: %d дат, пропущено: %d",
        len(results),
        skipped,
    )

    # ── Сохранение ────────────────────────────────────────────────────────
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, cls=_DecimalAwareEncoder, ensure_ascii=False, indent=2)

    logger.info("Результат записан в %s (%d записей)", output_path, len(results))
    return output_path


# ═══════════════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="KOLMO Kalculator — расчёт коэффициентов конверсии",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Рассчитать для одной даты (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--start",
        type=str,
        default=None,
        help="Начальная дата (YYYY-MM-DD, включительно)",
    )
    parser.add_argument(
        "--end",
        type=str,
        default=None,
        help="Конечная дата (YYYY-MM-DD, включительно)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Путь для выходного JSON (по умолчанию data/export/conversion_coefficients.json)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    out = Path(args.output) if args.output else OUTPUT_FILE
    try:
        path = run(
            start_date=args.start,
            end_date=args.end,
            single_date=args.date,
            output_path=out,
        )
        print(f"✅ Готово: {path}")
    except Exception:
        logger.exception("Ошибка при расчёте")
        sys.exit(1)


if __name__ == "__main__":
    main()
