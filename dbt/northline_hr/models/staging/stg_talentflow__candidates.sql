with source as (

    select * from {{ source('hr_raw', 'talentflow_candidates') }}

)

select
    candidate_id,
    trim(first_name)                          as first_name,
    trim(last_name)                           as last_name,
    lower(trim(personal_email))               as personal_email,
    regexp_replace(phone, r'[^0-9]', '')      as phone_digits,
    right(regexp_replace(phone, r'[^0-9]', ''), 10) as phone,
    cast(created_at as timestamp)             as created_at
from source