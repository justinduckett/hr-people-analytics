with employees_keyed as (

    select
        employees.*,
        person_map.person_key
    from {{ ref('stg_peoplecore__employees') }} as employees
    inner join {{ ref('int_peoplecore__person_map') }} as person_map
        using (employee_id)

),

person_summary as (

    select
        person_key,
        min(hire_date)   as first_hire_date,
        count(*)         as employment_record_count
    from employees_keyed
    group by person_key

),

-- Each person's most recent employment record supplies their
-- current-state attributes.
latest_record as (

    select *
    from employees_keyed
    qualify row_number() over (
        partition by person_key
        order by hire_date desc
    ) = 1

)

select
    latest_record.person_key,
    latest_record.first_name,
    latest_record.last_name,
    latest_record.personal_email,
    latest_record.employee_id        as latest_employee_id,
    latest_record.department,
    latest_record.job_title,
    latest_record.employment_type,
    latest_record.status,
    latest_record.hire_date          as latest_hire_date,
    latest_record.termination_date,
    person_summary.first_hire_date,
    person_summary.employment_record_count,
    person_summary.employment_record_count > 1 as is_rehire
from latest_record
inner join person_summary
    using (person_key)