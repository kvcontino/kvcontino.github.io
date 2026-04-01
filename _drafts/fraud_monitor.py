"""
Medi-Cal Managed Care Fraud Monitor
====================================
Runs a battery of SQL-based detection rules against 837/encounter data in Redshift,
computes a composite risk score per provider, and exports flagged results.

Usage:
    python fraud_monitor.py                  # full run, all rules
    python fraud_monitor.py --rules 1,3,5    # run specific rules only
    python fraud_monitor.py --dry-run        # print SQL without executing

Requirements:
    pip install redshift-connector pandas openpyxl
"""

import argparse
import os
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

try:
    import redshift_connector
except ImportError:
    sys.exit("Install redshift-connector: pip install redshift-connector")

from config import REDSHIFT, CLAIMS_TABLE, COLUMNS, THRESHOLDS, OUTPUT_DIR, LOOKBACK_MONTHS

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("fraud_monitor")

C = COLUMNS  # shorthand
T = THRESHOLDS

LOOKBACK_DATE = (datetime.today() - timedelta(days=LOOKBACK_MONTHS * 30)).strftime("%Y-%m-%d")


def get_connection():
    return redshift_connector.connect(**REDSHIFT)


def run_query(conn, sql, description, dry_run=False):
    """Execute SQL and return a DataFrame. If dry_run, just log the SQL."""
    log.info(f"Running: {description}")
    if dry_run:
        print(f"\n-- {description}\n{sql}\n")
        return pd.DataFrame()
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        cols = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        df = pd.DataFrame(rows, columns=cols)
        log.info(f"  → {len(df)} rows returned")
        return df
    except Exception as e:
        log.error(f"  Query failed: {e}")
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# Detection Rules
# ---------------------------------------------------------------------------
# Each rule returns a DataFrame with at minimum: provider_id, rule_id, rule_name,
# severity (1-10), and detail columns.

def rule_1_billing_impossibility(conn, dry_run=False):
    """Providers billing impossible daily volumes."""
    sql = f"""
    SELECT
        {C['provider_id']} AS provider_id,
        {C['service_date']} AS service_date,
        COUNT(DISTINCT {C['member_id']}) AS unique_patients,
        SUM({C['units']}) AS total_units,
        SUM({C['paid_amount']}) AS daily_paid
    FROM {CLAIMS_TABLE}
    WHERE {C['service_date']} >= '{LOOKBACK_DATE}'
      AND {C['claim_status']} = 'paid'
    GROUP BY 1, 2
    HAVING COUNT(DISTINCT {C['member_id']}) > {T['max_patients_per_day']}
        OR SUM({C['units']}) > {T['max_units_per_day']}
    ORDER BY unique_patients DESC
    """
    df = run_query(conn, sql, "Rule 1: Billing impossibility", dry_run)
    if not df.empty:
        df['rule_id'] = 1
        df['rule_name'] = 'billing_impossibility'
        df['severity'] = 7
    return df


def rule_2_upcoding(conn, dry_run=False):
    """Providers whose E&M code distribution skews high vs. specialty peers."""
    # E&M codes 99211-99215 (office outpatient) as the classic upcoding target
    sql = f"""
    WITH provider_em AS (
        SELECT
            {C['provider_id']} AS provider_id,
            {C['provider_specialty']} AS specialty,
            COUNT(*) AS total_em,
            SUM(CASE WHEN {C['procedure_code']} IN ('99214','99215') THEN 1 ELSE 0 END) AS high_em,
            SUM(CASE WHEN {C['procedure_code']} IN ('99214','99215') THEN 1 ELSE 0 END)::FLOAT
                / NULLIF(COUNT(*), 0) AS high_em_pct
        FROM {CLAIMS_TABLE}
        WHERE {C['procedure_code']} IN ('99211','99212','99213','99214','99215')
          AND {C['service_date']} >= '{LOOKBACK_DATE}'
          AND {C['claim_status']} = 'paid'
        GROUP BY 1, 2
        HAVING COUNT(*) >= {T['min_claims_for_scoring']}
    ),
    specialty_stats AS (
        SELECT
            specialty,
            AVG(high_em_pct) AS avg_high_pct,
            STDDEV(high_em_pct) AS std_high_pct
        FROM provider_em
        GROUP BY 1
        HAVING COUNT(*) >= 5
    )
    SELECT
        p.provider_id,
        p.specialty,
        p.total_em,
        p.high_em,
        ROUND(p.high_em_pct, 3) AS high_em_pct,
        ROUND(s.avg_high_pct, 3) AS peer_avg_pct,
        ROUND((p.high_em_pct - s.avg_high_pct) / NULLIF(s.std_high_pct, 0), 2) AS zscore
    FROM provider_em p
    JOIN specialty_stats s ON p.specialty = s.specialty
    WHERE (p.high_em_pct - s.avg_high_pct) / NULLIF(s.std_high_pct, 0) > {T['upcoding_zscore']}
    ORDER BY zscore DESC
    """
    df = run_query(conn, sql, "Rule 2: Upcoding detection", dry_run)
    if not df.empty:
        df['rule_id'] = 2
        df['rule_name'] = 'upcoding'
        df['severity'] = 6
    return df


def rule_3_duplicate_claims(conn, dry_run=False):
    """Near-duplicate claims: same provider, member, procedure within N days."""
    window = T['duplicate_window_days']
    sql = f"""
    WITH numbered AS (
        SELECT
            {C['claim_id']} AS claim_id,
            {C['provider_id']} AS provider_id,
            {C['member_id']} AS member_id,
            {C['procedure_code']} AS procedure_code,
            {C['service_date']} AS service_date,
            {C['paid_amount']} AS paid_amount,
            LAG({C['service_date']}) OVER (
                PARTITION BY {C['provider_id']}, {C['member_id']}, {C['procedure_code']}
                ORDER BY {C['service_date']}
            ) AS prev_date
        FROM {CLAIMS_TABLE}
        WHERE {C['service_date']} >= '{LOOKBACK_DATE}'
          AND {C['claim_status']} = 'paid'
    )
    SELECT
        provider_id,
        member_id,
        procedure_code,
        COUNT(*) AS duplicate_count,
        SUM(paid_amount) AS total_paid,
        MIN(service_date) AS first_date,
        MAX(service_date) AS last_date
    FROM numbered
    WHERE DATEDIFF(day, prev_date, service_date) BETWEEN 0 AND {window}
    GROUP BY 1, 2, 3
    HAVING COUNT(*) >= 3
    ORDER BY duplicate_count DESC
    """
    df = run_query(conn, sql, "Rule 3: Duplicate/near-duplicate claims", dry_run)
    if not df.empty:
        df['rule_id'] = 3
        df['rule_name'] = 'duplicate_claims'
        df['severity'] = 8
    return df


def rule_4_billing_velocity_spike(conn, dry_run=False):
    """Providers whose recent monthly volume spikes vs. their own baseline."""
    multiplier = T['velocity_spike_multiplier']
    sql = f"""
    WITH monthly AS (
        SELECT
            {C['provider_id']} AS provider_id,
            DATE_TRUNC('month', {C['service_date']}) AS month,
            COUNT(*) AS claim_count,
            SUM({C['paid_amount']}) AS monthly_paid
        FROM {CLAIMS_TABLE}
        WHERE {C['service_date']} >= '{LOOKBACK_DATE}'
          AND {C['claim_status']} = 'paid'
        GROUP BY 1, 2
    ),
    with_baseline AS (
        SELECT
            provider_id,
            month,
            claim_count,
            monthly_paid,
            AVG(claim_count) OVER (
                PARTITION BY provider_id
                ORDER BY month
                ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING
            ) AS trailing_avg,
            ROW_NUMBER() OVER (PARTITION BY provider_id ORDER BY month DESC) AS rn
        FROM monthly
    )
    SELECT
        provider_id,
        month,
        claim_count,
        ROUND(trailing_avg, 1) AS trailing_6mo_avg,
        monthly_paid,
        ROUND(claim_count::FLOAT / NULLIF(trailing_avg, 0), 2) AS spike_ratio
    FROM with_baseline
    WHERE rn <= 3  -- last 3 months
      AND trailing_avg IS NOT NULL
      AND claim_count > trailing_avg * {multiplier}
    ORDER BY spike_ratio DESC
    """
    df = run_query(conn, sql, "Rule 4: Billing velocity spike", dry_run)
    if not df.empty:
        df['rule_id'] = 4
        df['rule_name'] = 'velocity_spike'
        df['severity'] = 7
    return df


def rule_5_geographic_anomaly(conn, dry_run=False):
    """Members receiving services from distant providers on the same day."""
    # Simplified: flags when a member sees providers in different 3-digit ZIP prefixes same day.
    # For precise mileage, join a ZIP-centroid table.
    sql = f"""
    WITH daily_zips AS (
        SELECT
            {C['member_id']} AS member_id,
            {C['service_date']} AS service_date,
            {C['provider_id']} AS provider_id,
            LEFT({C['provider_zip']}, 3) AS zip3
        FROM {CLAIMS_TABLE}
        WHERE {C['service_date']} >= '{LOOKBACK_DATE}'
          AND {C['claim_status']} = 'paid'
          AND {C['provider_zip']} IS NOT NULL
    ),
    multi_zip AS (
        SELECT
            member_id,
            service_date,
            COUNT(DISTINCT zip3) AS distinct_zip3s,
            LISTAGG(DISTINCT zip3, ', ') WITHIN GROUP (ORDER BY zip3) AS zip3_list,
            LISTAGG(DISTINCT provider_id, ', ') WITHIN GROUP (ORDER BY provider_id) AS providers
        FROM daily_zips
        GROUP BY 1, 2
        HAVING COUNT(DISTINCT zip3) >= 2
    )
    SELECT *
    FROM multi_zip
    ORDER BY distinct_zip3s DESC, service_date DESC
    LIMIT 5000
    """
    df = run_query(conn, sql, "Rule 5: Geographic anomaly (same-day distant providers)", dry_run)
    if not df.empty:
        df['rule_id'] = 5
        df['rule_name'] = 'geographic_anomaly'
        df['severity'] = 6
    return df


def rule_6_rendering_billing_mismatch(conn, dry_run=False):
    """Providers where rendering ≠ billing on a suspicious share of claims."""
    pct = T['reassignment_pct_flag']
    sql = f"""
    SELECT
        {C['billing_provider']} AS billing_provider,
        COUNT(*) AS total_claims,
        SUM(CASE WHEN {C['provider_id']} != {C['billing_provider']} THEN 1 ELSE 0 END) AS reassigned,
        ROUND(
            SUM(CASE WHEN {C['provider_id']} != {C['billing_provider']} THEN 1 ELSE 0 END)::FLOAT
            / NULLIF(COUNT(*), 0), 3
        ) AS reassignment_pct,
        SUM({C['paid_amount']}) AS total_paid
    FROM {CLAIMS_TABLE}
    WHERE {C['service_date']} >= '{LOOKBACK_DATE}'
      AND {C['claim_status']} = 'paid'
    GROUP BY 1
    HAVING COUNT(*) >= {T['min_claims_for_scoring']}
       AND SUM(CASE WHEN {C['provider_id']} != {C['billing_provider']} THEN 1 ELSE 0 END)::FLOAT
           / NULLIF(COUNT(*), 0) > {pct}
    ORDER BY reassignment_pct DESC
    """
    df = run_query(conn, sql, "Rule 6: Rendering/billing provider mismatch", dry_run)
    if not df.empty:
        df['rule_id'] = 6
        df['rule_name'] = 'rendering_billing_mismatch'
        df['severity'] = 7
    return df


def rule_7_paid_billed_ratio(conn, dry_run=False):
    """Providers with suspiciously high paid-to-billed ratios (possible fee gaming)."""
    cap = T['paid_billed_ratio_cap']
    sql = f"""
    SELECT
        {C['provider_id']} AS provider_id,
        COUNT(*) AS claim_count,
        SUM({C['billed_amount']}) AS total_billed,
        SUM({C['paid_amount']}) AS total_paid,
        ROUND(SUM({C['paid_amount']})::FLOAT / NULLIF(SUM({C['billed_amount']}), 0), 4) AS paid_billed_ratio
    FROM {CLAIMS_TABLE}
    WHERE {C['service_date']} >= '{LOOKBACK_DATE}'
      AND {C['claim_status']} = 'paid'
      AND {C['billed_amount']} > 0
    GROUP BY 1
    HAVING COUNT(*) >= {T['min_claims_for_scoring']}
       AND SUM({C['paid_amount']})::FLOAT / NULLIF(SUM({C['billed_amount']}), 0) > {cap}
    ORDER BY paid_billed_ratio DESC
    """
    df = run_query(conn, sql, "Rule 7: Paid/billed ratio anomaly", dry_run)
    if not df.empty:
        df['rule_id'] = 7
        df['rule_name'] = 'paid_billed_ratio_anomaly'
        df['severity'] = 5
    return df


# ---------------------------------------------------------------------------
# Composite Scoring
# ---------------------------------------------------------------------------

RULES = {
    1: rule_1_billing_impossibility,
    2: rule_2_upcoding,
    3: rule_3_duplicate_claims,
    4: rule_4_billing_velocity_spike,
    5: rule_5_geographic_anomaly,
    6: rule_6_rendering_billing_mismatch,
    7: rule_7_paid_billed_ratio,
}


def compute_provider_scores(rule_results):
    """
    Aggregate rule hits into a single risk score per provider.
    Score = sum of severity for each rule triggered, weighted by frequency.
    """
    all_flags = []
    for df in rule_results:
        if df.empty:
            continue
        if 'provider_id' in df.columns:
            summary = df.groupby('provider_id').agg(
                hits=('rule_id', 'count'),
                severity=('severity', 'first'),
                rule_id=('rule_id', 'first'),
                rule_name=('rule_name', 'first'),
            ).reset_index()
            summary['rule_score'] = summary['severity'] * summary['hits'].clip(upper=10)
            all_flags.append(summary[['provider_id', 'rule_id', 'rule_name', 'rule_score']])

    if not all_flags:
        log.warning("No flags generated across any rules.")
        return pd.DataFrame()

    flags = pd.concat(all_flags, ignore_index=True)

    # Composite score per provider
    scores = flags.groupby('provider_id').agg(
        total_score=('rule_score', 'sum'),
        rules_triggered=('rule_id', 'nunique'),
        rule_list=('rule_name', lambda x: ', '.join(sorted(set(x)))),
    ).reset_index().sort_values('total_score', ascending=False)

    # Tier assignment
    scores['risk_tier'] = pd.cut(
        scores['total_score'],
        bins=[0, 10, 25, 50, float('inf')],
        labels=['Low', 'Medium', 'High', 'Critical'],
    )

    return scores


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Medi-Cal Managed Care Fraud Monitor")
    parser.add_argument("--rules", type=str, default=None,
                        help="Comma-separated rule IDs to run (e.g. 1,3,5). Default: all.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print SQL without executing.")
    args = parser.parse_args()

    # Determine which rules to run
    if args.rules:
        rule_ids = [int(r.strip()) for r in args.rules.split(",")]
    else:
        rule_ids = sorted(RULES.keys())

    log.info(f"Fraud Monitor starting — rules: {rule_ids}, lookback: {LOOKBACK_DATE}")

    # Output directory
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    conn = None if args.dry_run else get_connection()

    try:
        # Run each rule
        rule_results = []
        for rid in rule_ids:
            if rid not in RULES:
                log.warning(f"Unknown rule ID {rid}, skipping.")
                continue
            df = RULES[rid](conn, dry_run=args.dry_run)
            rule_results.append(df)

            # Save individual rule output
            if not df.empty:
                outfile = os.path.join(OUTPUT_DIR, f"rule_{rid}_{timestamp}.csv")
                df.to_csv(outfile, index=False)
                log.info(f"  Saved: {outfile}")

        if args.dry_run:
            log.info("Dry run complete. No data written.")
            return

        # Composite scoring
        scores = compute_provider_scores(rule_results)
        if not scores.empty:
            scores_file = os.path.join(OUTPUT_DIR, f"provider_scores_{timestamp}.csv")
            scores.to_csv(scores_file, index=False)
            log.info(f"Provider scores saved: {scores_file}")

            # Summary
            log.info("\n--- Risk Tier Summary ---")
            tier_summary = scores['risk_tier'].value_counts().sort_index()
            for tier, count in tier_summary.items():
                log.info(f"  {tier}: {count} providers")

            # Top 20
            log.info("\n--- Top 20 Highest-Risk Providers ---")
            top = scores.head(20)
            for _, row in top.iterrows():
                log.info(
                    f"  {row['provider_id']}  score={row['total_score']}  "
                    f"tier={row['risk_tier']}  rules=[{row['rule_list']}]"
                )

            # Excel workbook with all sheets for Tableau / manual review
            xlsx_file = os.path.join(OUTPUT_DIR, f"fraud_monitor_report_{timestamp}.xlsx")
            with pd.ExcelWriter(xlsx_file, engine='openpyxl') as writer:
                scores.to_excel(writer, sheet_name='Provider Scores', index=False)
                for i, df in enumerate(rule_results):
                    if not df.empty:
                        rid = rule_ids[i]
                        sheet = f"Rule {rid}"
                        df.to_excel(writer, sheet_name=sheet, index=False)
            log.info(f"Full report saved: {xlsx_file}")

        else:
            log.info("No providers flagged. Review thresholds if this seems wrong.")

    finally:
        if conn:
            conn.close()
            log.info("Connection closed.")


if __name__ == "__main__":
    main()
