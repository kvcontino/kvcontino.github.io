"""
Fraud Monitor Configuration
Adjust connection details and detection thresholds to match your environment.
"""

# --- Redshift Connection ---
REDSHIFT = {
    "host": "your-cluster.region.redshift.amazonaws.com",
    "port": 5439,
    "dbname": "your_db",
    "user": "your_user",
    "password": "your_password",  # Better: use env var or AWS Secrets Manager
}

# --- Schema / Table References ---
# Adjust these to match your actual Redshift table and column names.
CLAIMS_TABLE = "claims.encounters"

# Column mappings: keys are what the tool expects, values are your actual column names.
COLUMNS = {
    "claim_id":          "claim_id",
    "member_id":         "member_id",
    "provider_id":       "rendering_provider_id",
    "billing_provider":  "billing_provider_id",
    "service_date":      "service_from_date",
    "procedure_code":    "procedure_code",
    "diagnosis_code":    "primary_diagnosis_code",  # ICD-10
    "paid_amount":       "paid_amount",
    "billed_amount":     "billed_amount",
    "units":             "service_units",
    "place_of_service":  "place_of_service_code",
    "provider_specialty": "provider_specialty_code",
    "provider_zip":      "provider_zip",
    "member_zip":        "member_zip",
    "plan_id":           "managed_care_plan_id",
    "claim_status":      "claim_status",  # paid, denied, etc.
}

# --- Detection Thresholds ---
# These are starting points. Tune after your first run based on false-positive volume.

THRESHOLDS = {
    # Max reasonable patients per provider per day before flagging
    "max_patients_per_day": 40,

    # Max reasonable service units per provider per day
    "max_units_per_day": 80,

    # Upcoding: flag if provider's high-complexity E&M share exceeds
    # peer specialty average by this many standard deviations
    "upcoding_zscore": 2.0,

    # Duplicate window: same provider + member + procedure within N days
    "duplicate_window_days": 7,

    # Billing velocity: flag if monthly claim count exceeds trailing
    # 6-month average by this multiplier
    "velocity_spike_multiplier": 2.5,

    # Geographic: flag if member sees providers in ZIPs > N miles apart on same day
    # (requires ZIP-centroid reference; approximate with first-3-digits if needed)
    "geo_distance_flag_miles": 100,

    # Minimum claims for a provider to be scored (avoids noise from low-volume)
    "min_claims_for_scoring": 50,

    # Paid-to-billed ratio anomaly: flag if provider's ratio is above this
    "paid_billed_ratio_cap": 0.98,

    # Percentage of services billed under a different rendering vs billing provider
    "reassignment_pct_flag": 0.80,
}

# --- Output ---
OUTPUT_DIR = "./fraud_output"

# --- Lookback period (months) ---
LOOKBACK_MONTHS = 12
