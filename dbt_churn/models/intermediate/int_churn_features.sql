WITH customers AS (
    SELECT * FROM {{ ref('stg_telco__customers') }}
),
final AS (
    SELECT
        *,
        CASE
            WHEN tenure < 12 THEN 'New'
            WHEN tenure < 48 THEN 'Mid'
            ELSE 'Loyal'
        END AS customer_tenure_segment,
        CAST(
            CASE WHEN churn = 'Yes' THEN 1
            ELSE 0
            END AS INTEGER
            )
        AS has_churned
    FROM customers
)
SELECT * FROM final