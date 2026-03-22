# Medicaid & CHIP Program Monitor

State-level dashboard for monitoring Medicaid enrollment, managed care penetration, and per-member expenditures. Data fetched live from [data.medicaid.gov](https://data.medicaid.gov) via the CMS DKAN API.

## What's in it

| Panel | Data source | Update cadence |
|-------|-------------|----------------|
| Enrollment trend (line) | data.medicaid.gov `6165f45b` dataset | Monthly |
| State snapshot choropleth | Same | Monthly |
| Percent-change choropleth | Same (two-period calculation) | Monthly |
| Managed care % | healthdata.gov `m563-snjf` (Socrata) | Annual |
| PMPM expenditures | data.medicaid.gov MBES dataset (auto-discovered) | Quarterly/annual |

### Enrollment types available
- Total Medicaid & CHIP
- Medicaid Only
- CHIP Only
- Children
- Adults

### Geography filters
- All states (default: regional aggregates on trend chart)
- Census Regions: Northeast, Midwest, South, West
- Census Divisions (9 divisions)
- Individual states + DC

## Deployment to GitHub Pages

1. Copy this directory to the root of your GitHub repo (or a `/docs` folder)
2. In **Settings → Pages**, set source to `main` branch, `/root` (or `/docs`)
3. No build step required — pure static HTML/CSS/JS with ES modules

```
your-repo/
├── index.html
├── css/styles.css
├── js/
│   ├── main.js
│   ├── api.js
│   ├── state.js
│   ├── filters.js
│   ├── trend.js
│   └── geo.js
└── data/
    ├── census-regions.json
    └── state-populations.json
```

### Custom domain
Add a `CNAME` file with your domain name in the repo root.

## Data notes

**Enrollment data** (`6165f45b`): Contains both Preliminary (P) and Updated/Final (U) rows per state per period. The dashboard uses Final/Updated rows only (`final_report = Y`). Data typically lags 3–6 months from the current date.

**Managed care data** (`m563-snjf` on healthdata.gov): Annual point-in-time snapshot. The trend chart for managed care will therefore show annual rather than monthly granularity. If healthdata.gov CORS changes, this metric will show an error; fallback to the GitHub Actions approach below is recommended.

**PMPM data**: The MBES expenditure dataset is discovered at runtime by querying known CMS DKAN UUIDs. If auto-discovery fails (API changes, CORS issues), this metric will be unavailable. See the GitHub Actions pre-fetch approach below.

## Optional: GitHub Actions pre-fetch (recommended for PMPM / managed care)

For data sources that don't support CORS from browsers, or to reduce client-side API calls, add a GitHub Actions workflow that pre-fetches data as static JSON:

```yaml
# .github/workflows/fetch-data.yml
name: Refresh Medicaid Data
on:
  schedule:
    - cron: '0 8 1 * *'  # First of each month
  workflow_dispatch:

jobs:
  fetch:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Fetch enrollment data
        run: |
          curl -s "https://data.medicaid.gov/api/1/datastore/query/6165f45b-ca93-5bb5-9d06-db29c692a360/0?limit=10000&conditions[0][property]=final_report&conditions[0][value]=Y&conditions[0][operator]=%3D" \
            > data/enrollment.json
      - name: Fetch managed care data
        run: |
          curl -s "https://healthdata.gov/resource/m563-snjf.json?$limit=5000" \
            > data/managed-care.json
      - name: Commit updated data
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/
          git diff --staged --quiet || git commit -m "chore: refresh Medicaid data $(date +%Y-%m)"
          git push
```

When `data/enrollment.json` is present, `api.js` will use the local file instead of the live API (modify `fetchEnrollment` to check for this file first).

## Sources

- Enrollment: CMS Medicaid & CHIP Enrollment Data Highlights — [data.medicaid.gov](https://data.medicaid.gov/dataset/6165f45b-ca93-5bb5-9d06-db29c692a360)
- Managed care: Share of Medicaid Enrollees in Managed Care — [healthdata.gov](https://healthdata.gov/d/m563-snjf)
- State populations: U.S. Census Bureau, 2023 estimates
- Census regions/divisions: U.S. Census Bureau geographic classifications
- TopoJSON: [us-atlas](https://github.com/topojson/us-atlas) (Albers USA projection, Census Bureau TIGER/Line)

## Known limitations

- Territories (PR, GU, VI, AS, MP) appear in trend data but not on the choropleth (not in the us-atlas TopoJSON)
- Managed care and PMPM data have lower time resolution (annual/quarterly vs monthly for enrollment)
- Data currency typically lags 3–6 months; the dashboard displays the latest available period
