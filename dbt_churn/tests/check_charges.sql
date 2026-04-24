with validation as (
    select
        customer_id,
        tenure,
        monthly_charges,
        total_charges,
        round(monthly_charges * tenure, 2) as expected_total
    from {{ ref('stg_telco__customers') }}
    where total_charges is not null
      and not (total_charges = 0 and tenure <= 1)
      and abs(total_charges - (monthly_charges * tenure)) > 100
)
select * from validation