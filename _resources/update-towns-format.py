import re

FILENAME = 'nny-toponyms.html'

with open(FILENAME, 'r') as f:
    content = f.read()

# 1. Reformat every TOWNS entry from:
#      'name': ['X'],
#      'name': ['X','Y'],
#    to:
#      'name': { cats: ['X'], desc: '' },
#      'name': { cats: ['X','Y'], desc: '' },
content = re.sub(
    r"('[\w\s]+':\s*)(\[.*?\])(,)",
    r"\1{ cats: \2, desc: '' }\3",
    content
)

# 2. Update the three read sites:

# Feature processing: TOWNS[name] → TOWNS[name].cats
content = content.replace(
    'var cats = TOWNS[name] || [];',
    'var entry = TOWNS[name]; var cats = entry ? entry.cats : [];'
)

# Add desc to feature properties
content = content.replace(
    "p._cats   = cats;",
    "p._cats   = cats;\n        p._desc   = entry ? (entry.desc || '') : '';"
)

# Mouseover: add description line after category label
content = content.replace(
    "'<div class=\"tt-cat\">'+catLabels+'</div>';",
    "'<div class=\"tt-cat\">'+catLabels+'</div>'+\n            (d.properties._desc ? '<div class=\"tt-desc\">'+d.properties._desc+'</div>' : '');"
)

with open(FILENAME, 'w') as f:
    f.write(content)

print('Done. Verify a few TOWNS entries look right, then add your descriptions.')
