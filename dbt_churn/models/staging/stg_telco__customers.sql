WITH source AS (
    SELECT * FROM {{ ref('telco_churn') }}
),
renamed AS (
    SELECT
        customerID AS customer_id,
        gender,
        SeniorCitizen AS senior_citizen,
        Partner AS partner,
        Dependents AS dependents,
        tenure,
        PhoneService AS phone_service,
        MultipleLines AS multiple_lines,
        InternetService AS internet_service,
        OnlineSecurity AS online_security,
        OnlineBackup AS online_backup,
        DeviceProtection AS device_protection,
        TechSupport AS tech_support,
        StreamingTV AS streaming_tv,
        StreamingMovies AS streaming_movies,
        Contract AS contract,
        PaperlessBilling AS paperless_billing,
        PaymentMethod AS payment_method,
        MonthlyCharges AS monthly_charges,
        TotalCharges AS total_charges,
        Churn AS churn
    FROM source
)
SELECT * FROM renamed