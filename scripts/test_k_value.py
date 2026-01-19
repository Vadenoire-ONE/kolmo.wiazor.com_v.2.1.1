from decimal import Decimal
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "src"))

from kolmo.computation.transformer import RateTransformer

transformer = RateTransformer()

# Test the values
eur_usd = Decimal("100.0")
eur_cny = Decimal("0.001")

# Calculate what K would be
r_me4u = eur_usd / eur_cny
r_iou2 = Decimal("1") / eur_usd
r_uome = eur_cny

kolmo_value = r_me4u * r_iou2 * r_uome

print(f"eur_usd: {eur_usd}")
print(f"eur_cny: {eur_cny}")
print(f"r_me4u: {r_me4u}")
print(f"r_iou2: {r_iou2}")
print(f"r_uome: {r_uome}")
print(f"kolmo_value: {kolmo_value}")
print(f"deviation: {abs(kolmo_value - Decimal('1.0'))}")
print(f"tolerance: 0.05")
print(f"Would fail?: {abs(kolmo_value - Decimal('1.0')) > Decimal('0.05')}")
