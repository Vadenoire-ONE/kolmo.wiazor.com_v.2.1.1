from decimal import Decimal, getcontext
getcontext().prec = 40

eur_usd = Decimal('1.0353')
eur_cny = Decimal('7.5280')

r_me4u = eur_usd / eur_cny
r_iou2 = Decimal('1') / eur_usd
r_uome = eur_cny
kolmo = r_me4u * r_iou2 * r_uome

print('r_me4u =', r_me4u)
print('r_iou2 =', r_iou2)
print('r_uome =', r_uome)
print('kolmo =', kolmo)

# distances
from decimal import Decimal

def dist(x):
    return abs(x - Decimal('1')) * Decimal('100')

print('dist_me4u =', dist(r_me4u))
print('dist_iou2 =', dist(r_iou2))
print('dist_uome =', dist(r_uome))
