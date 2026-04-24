select customer_id
from {{ ref('stg_telco__customers') }}
where phone_service = 'No'
  and multiple_lines = 'Yes'