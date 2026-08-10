with employees as (

    select * from {{ ref('stg_peoplecore__employees') }}

),

-- Rule 1: records sharing a personal email belong to one person.
-- The window function stamps every record with the smallest
-- employee_id among all records having the same email.
email_links as (

    select
        employee_id,
        min(employee_id) over (partition by personal_email) as linked_key,
        'shared_email' as match_rule
    from employees
    where personal_email is not null
    qualify count(*) over (partition by personal_email) > 1

),

-- Rule 2: same full name AND strictly sequential employment
-- (the earlier record terminated before the later one began).
-- Two records with overlapping employment and the same name are
-- different people and must never link (the Sarah Lee guard).
name_links as (

    select
        later.employee_id,
        earlier.employee_id as linked_key,
        'same_name_sequential' as match_rule
    from employees as earlier
    inner join employees as later
        on  earlier.first_name = later.first_name
        and earlier.last_name  = later.last_name
        and earlier.employee_id != later.employee_id
        and earlier.termination_date is not null
        and earlier.termination_date < later.hire_date

),

-- Every record is also always linked to itself, so unmatched
-- records become their own person.
all_links as (

    select employee_id, employee_id as linked_key, 'self' as match_rule
    from employees

    union all
    select employee_id, linked_key, match_rule from email_links

    union all
    select employee_id, linked_key, match_rule from name_links

)

select
    employee_id,
    min(linked_key) as person_key,
    string_agg(distinct match_rule order by match_rule) as match_basis
from all_links
group by employee_id