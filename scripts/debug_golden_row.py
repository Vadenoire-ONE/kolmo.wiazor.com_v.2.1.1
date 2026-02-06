from decimal import Decimal, getcontext
import csv
from pathlib import Path

getcontext().prec = 28

from kolmo.computation.transformer import RateTransformer
from kolmo.computation.calculator import KOLMOCalculator

GOLDEN = Path(__file__).parent.parent / 'tests' / 'golden' / 'kolmo_reference_data.csv'

with open(GOLDEN, newline='') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row['date'] == '2025-01-02':
            print('CSV row:')
            for k in ['eur_usd','eur_cny','r_me4u','r_iou2','r_uome','kolmo_value_exact','winner']:
                print(f'  {k}: {row.get(k)!r}')

            eur_usd = Decimal(row['eur_usd'])
            eur_cny = Decimal(row['eur_cny'])

            tr = RateTransformer()
            rates = tr.transform(eur_usd, eur_cny)
            calc = KOLMOCalculator()
            kolmo = calc.compute_kolmo_value(rates.r_me4u, rates.r_iou2, rates.r_uome)

            print('\nComputed by transformer:')
            print(f'  r_me4u: {rates.r_me4u}')
            print(f'  r_iou2: {rates.r_iou2}')
            print(f'  r_uome: {rates.r_uome}')
            print(f'  kolmo:  {kolmo}')
            break
else:
    print('Row not found')
