WITH features AS (
    SELECT * FROM {{ ref('int_churn_features') }}
),
aggregated AS (
    SELECT
        customer_tenure_segment,
        contract,
        COUNT(*) AS total_customers,
        SUM(CASE WHEN churn = 'Yes' THEN 1 ELSE 0 END) AS churned_customers,
        ROUND(100.0 * SUM(CASE WHEN churn = 'Yes' THEN 1 ELSE 0 END) / COUNT(*), 2) AS churn_rate
    FROM features
    GROUP BY 1, 2
)
SELECT * FROM aggregated