WITH customers AS (
    SELECT * FROM {{ ref('stg_telco__customers') }}
),
final AS (
    SELECT
        customer_id,
        gender,
        senior_citizen,
        partner,
        dependents,
        tenure,
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
        monthly_charges,
        -- Imputation: new clients (tenure=0) have their total_charges as NULL
        COALESCE(CAST(total_charges AS double), 0) AS total_charges,
        churn,
        -- We also add customer_tenure_segment because their period of time with their subscription can be valuable information
        CASE
            WHEN tenure < 12 THEN 'New'
            WHEN tenure < 48 THEN 'Mid'
            ELSE 'Loyal'
        END AS customer_tenure_segment
    FROM customers
)
SELECT * FROM final