WITH source AS (
    SELECT * FROM read_json_auto('s3://churn-data-lake/telco/telco_churn/**/*.jsonl.gz')
)
SELECT
    customer_id,
    gender,
    CAST(senior_citizen AS INTEGER) AS senior_citizen,
    partner,
    dependents,
    CAST(tenure AS INTEGER) AS tenure,
    phone_service,
    multiple_lines,
    internet_service,
    online_security,
    online_backup,
    device_protection,
    tech_support,
    streaming_tv,
    streaming_movies,
    contract,
    paperless_billing,
    payment_method,
    CAST(monthly_charges AS DOUBLE) AS monthly_charges,
    CAST(NULLIF(TRIM(total_charges), '') AS DOUBLE) AS total_charges,
    churn
FROM source