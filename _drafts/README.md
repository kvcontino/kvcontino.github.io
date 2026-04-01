# Medi-Cal Managed Care Fraud Monitor

Automated detection pipeline for common Medicaid managed care fraud patterns. Runs SQL-based rules against 837/encounter data in Redshift, scores providers by composite risk, and exports results for review or Tableau ingestion.

## Setup

```bash
pip install redshift-connector pandas openpyxl
```

Edit `config.py`:
1. Set your Redshift connection details
2. Map `COLUMNS` to your actual table/column names
3. Adjust `THRESHOLDS` (defaults are conservative starting points)

## Usage

```bash
# Full run — all 7 rules
python fraud_monitor.py

# Run specific rules only
python fraud_monitor.py --rules 1,3,5

# Preview SQL without hitting Redshift
python fraud_monitor.py --dry-run
```

## Detection Rules

| Rule | What it catches | Severity |
|------|----------------|----------|
| 1 | Billing impossibility (>40 patients/day or >80 units/day) | 7 |
| 2 | Upcoding (E&M distribution vs. specialty peers, z-score) | 6 |
| 3 | Duplicate/near-duplicate claims (same provider+member+CPT within 7 days) | 8 |
| 4 | Billing velocity spike (monthly volume vs. own trailing 6-month average) | 7 |
| 5 | Geographic anomaly (member sees providers in distant ZIPs same day) | 6 |
| 6 | Rendering ≠ billing provider on >80% of claims | 7 |
| 7 | Paid-to-billed ratio anomaly (>98%, possible fee schedule gaming) | 5 |

## Output

All output lands in `./fraud_output/`:
- `provider_scores_TIMESTAMP.csv` — composite risk score per provider, tiered Low/Medium/High/Critical
- `rule_N_TIMESTAMP.csv` — detailed hits per rule
- `fraud_monitor_report_TIMESTAMP.xlsx` — all of the above in one workbook (tabs per rule + scores)

## Connecting to Tableau

Point Tableau at the Excel workbook or CSVs. Useful views:
- **Provider scorecard**: join `provider_scores` to your provider reference table, map risk tier to color
- **Rule drill-down**: filter by rule, sort by severity and dollar exposure
- **Time trend**: use Rule 4 velocity data to show providers whose volume is diverging from baseline

## Tuning

After your first run, expect noise. Two levers:
- `min_claims_for_scoring`: raise to filter out low-volume providers (currently 50)
- Individual thresholds in `THRESHOLDS`: e.g., `max_patients_per_day` at 40 may be too low for large group practices — adjust per specialty if needed

## Automation

Schedule with cron or Airflow:
```bash
# Weekly run, Sunday 2 AM
0 2 * * 0 cd /path/to/fraud_monitor && python fraud_monitor.py >> /var/log/fraud_monitor.log 2>&1
```

## Extending

To add a new rule:
1. Write a function matching the pattern in `fraud_monitor.py` (returns DataFrame with provider_id, rule_id, rule_name, severity)
2. Add it to the `RULES` dict
3. Add any new thresholds to `config.py`

Candidates for future rules:
- **Procedure-diagnosis mismatch**: flag CPT codes billed with clinically unsupported ICD-10s (requires a crosswalk table)
- **Phantom provider detection**: cross-reference provider IDs against NPPES/Medi-Cal enrollment; flag providers billing but not in registry
- **Beneficiary sharing rings**: network analysis of providers sharing unusual overlap in member panels
- **Weekend/holiday billing**: flag high volumes on days the provider's facility type shouldn't be open
