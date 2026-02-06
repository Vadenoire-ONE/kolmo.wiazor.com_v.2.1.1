import json
p='data/export/kolmo_history.json'
with open(p,'r',encoding='utf-8') as f:
    j=json.load(f)
print('len=',len(j))
print('last=', j[-1]['date'])
