from decimal import Decimal
from kolmo.computation.transformer import RateTransformer
from kolmo.computation.calculator import KOLMOCalculator
from kolmo.computation.winner import WinnerSelector

eur_usd = Decimal("1.042500")
eur_cny = Decimal("6.987000")

t = RateTransformer()
rates = t.transform(eur_usd, eur_cny)

calc = KOLMOCalculator()
kolmo = calc.compute_kolmo_value(rates.r_me4u, rates.r_iou2, rates.r_uome)
dist_me4u = calc.compute_distance(rates.r_me4u)
dist_iou2 = calc.compute_distance(rates.r_iou2)
dist_uome = calc.compute_distance(rates.r_uome)

# Assuming no previous day (first day) — set prev distances to None
rel_me4u = calc.compute_relativepath(dist_me4u, None)
rel_iou2 = calc.compute_relativepath(dist_iou2, None)
rel_uome = calc.compute_relativepath(dist_uome, None)

selector = WinnerSelector()
winner, reason = selector.select(rel_me4u, rel_iou2, rel_uome)

print("rates:", rates)
print("kolmo_value_exact:", kolmo)
print("dist_me4u:", dist_me4u)
print("dist_iou2:", dist_iou2)
print("dist_uome:", dist_uome)
print("relpath_me4u:", rel_me4u)
print("relpath_iou2:", rel_iou2)
print("relpath_uome:", rel_uome)
print("winner:", winner.value)
print("reason:", reason)