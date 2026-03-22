import csv, json

STATE_ABBR = {
    'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR',
    'California': 'CA', 'Colorado': 'CO', 'Connecticut': 'CT', 'Delaware': 'DE',
    'District of Columbia': 'DC', 'Florida': 'FL', 'Georgia': 'GA', 'Hawaii': 'HI',
    'Idaho': 'ID', 'Illinois': 'IL', 'Indiana': 'IN', 'Iowa': 'IA',
    'Kansas': 'KS', 'Kentucky': 'KY', 'Louisiana': 'LA', 'Maine': 'ME',
    'Maryland': 'MD', 'Massachusetts': 'MA', 'Michigan': 'MI', 'Minnesota': 'MN',
    'Mississippi': 'MS', 'Missouri': 'MO', 'Montana': 'MT', 'Nebraska': 'NE',
    'Nevada': 'NV', 'New Hampshire': 'NH', 'New Jersey': 'NJ', 'New Mexico': 'NM',
    'New York': 'NY', 'North Carolina': 'NC', 'North Dakota': 'ND', 'Ohio': 'OH',
    'Oklahoma': 'OK', 'Oregon': 'OR', 'Pennsylvania': 'PA', 'Rhode Island': 'RI',
    'South Carolina': 'SC', 'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX',
    'Utah': 'UT', 'Vermont': 'VT', 'Virginia': 'VA', 'Washington': 'WA',
    'West Virginia': 'WV', 'Wisconsin': 'WI', 'Wyoming': 'WY',
    'Puerto Rico': 'PR', 'Guam': 'GU', 'Virgin Islands': 'VI',
    'Northern Mariana Islands': 'MP', 'American Samoa': 'AS'
}

def parse_num(val):
    if not val or val.strip() in ('', 'N/A', 'n/a', '*','--'):
        return None
    return float(val.replace(',', '').replace('%', '').strip())

rows = []
with open('/tmp/managed-care.csv') as f:
    for row in csv.DictReader(f):
        state_name = row.get('State', '').strip()
        abbr = STATE_ABBR.get(state_name)
        if not abbr:
            continue  # skip TOTALS and unrecognized rows
        year = row.get('Year', '').strip() or row.get('year', '').strip()
        rows.append({
            'state_abbreviation': abbr,
            'year': year,
            'total_medicaid_enrollees': parse_num(row.get('Total Medicaid Enrollees')),
            'enrolled_any': parse_num(row.get('Individuals Enrolled (Any)')),
            'pct_any': parse_num(row.get('Percent of all Medicaid enrollees (Any)')),
            'enrolled_comprehensive': parse_num(row.get('Individuals Enrolled (Comprehensive)')),
            'pct_comprehensive': parse_num(row.get('Percent of all Medicaid enrollees (Comprehensive)')),
        })

with open('_resources/mcaid/managed-care.json', 'w') as f:
    json.dump(rows, f)

print(f'Rows written: {len(rows)}')
if rows:
    print(f'Sample: {rows[0]}')
