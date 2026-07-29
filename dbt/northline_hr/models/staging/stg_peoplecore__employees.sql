with source as (

    select * from {{ source('hr_raw', 'peoplecore_employees') }}

),

department_mapping as (

    select * from {{ ref('department_mapping') }}

),

cleaned as (

    select
        employee_id,
        trim(first_name)                          as first_name,
        trim(last_name)                           as last_name,
        lower(trim(work_email))                   as work_email,
        nullif(lower(trim(personal_email)), '')   as personal_email,
        trim(department)                          as department_raw,
        trim(job_title)                           as job_title,
        upper(trim(employment_type))              as employment_type,
        nullif(trim(salary_band), '')             as salary_band,
        cast(hire_date as date)                   as hire_date,
        cast(termination_date as date)            as termination_date,
        status,
        cast(last_modified as timestamp)          as last_modified_at
    from source

)

select
    cleaned.employee_id,
    cleaned.first_name,
    cleaned.last_name,
    cleaned.work_email,
    cleaned.personal_email,
    department_mapping.department,
    cleaned.department_raw,
    cleaned.job_title,
    cleaned.employment_type,
    cleaned.salary_band,
    cleaned.hire_date,
    cleaned.termination_date,
    cleaned.status,
    cleaned.last_modified_at
from cleaned
left join department_mapping
    on lower(cleaned.department_raw) = department_mapping.source_department