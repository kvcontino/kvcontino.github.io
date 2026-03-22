import csv, json

rows = []
with open('/tmp/managed-care.csv') as f:
    for row in csv.DictReader(f):
        row['year'] = '2024'
        rows.append(row)

out = '_resources/mcaid/managed-care.json'
with open(out, 'w') as f:
    json.dump(rows, f)

print(f'Rows written: {len(rows)}')
