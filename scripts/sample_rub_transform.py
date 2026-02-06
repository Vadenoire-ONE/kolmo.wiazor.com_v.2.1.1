from decimal import Decimal
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from kolmo.computation.transformer import RateTransformer
from kolmo.computation.calculator import KOLMOCalculator

# Пример входных RUB-курсов (RUB per USD, RUB per CNY)
examples = [
    (Decimal('82.50'), Decimal('11.90')),
    (Decimal('75.30'), Decimal('12.60')),
    (Decimal('90.10'), Decimal('14.00'))
]

t = RateTransformer()
calc = KOLMOCalculator()

for rub_usd, rub_cny in examples:
    rates = t.transform(rub_usd=rub_usd, rub_cny=rub_cny)
    kolmo = calc.compute_kolmo_value(rates.r_me4u, rates.r_iou2, rates.r_uome)
    dist_me4u = calc.compute_distance(rates.r_me4u)
    dist_iou2 = calc.compute_distance(rates.r_iou2)
    dist_uome = calc.compute_distance(rates.r_uome)

    print(f"INPUT: rub_usd={rub_usd}, rub_cny={rub_cny}")
    print(f" -> r_me4u = {rates.r_me4u}")
    print(f" -> r_iou2 = {rates.r_iou2}")
    print(f" -> r_uome = {rates.r_uome}")
    print(f" kolmo_value = {kolmo}")
    print(f" distances (me4u,iou2,uome) = {dist_me4u}, {dist_iou2}, {dist_uome}")
    print('-' * 60)
