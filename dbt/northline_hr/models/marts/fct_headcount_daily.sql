with dates as (

    select date_day from {{ ref('dim_date') }}

),

employment_records as (

    select
        employee_id,
        department,
        employment_type,
        hire_date,
        termination_date
    from {{ ref('stg_peoplecore__employees') }}

)

select
    dates.date_day,
    employment_records.department,
    employment_records.employment_type,
    count(*) as headcount
from dates
inner join employment_records
    on  employment_records.hire_date <= dates.date_day
    and (
        employment_records.termination_date is null
        or employment_records.termination_date > dates.date_day
    )
group by 1, 2, 3