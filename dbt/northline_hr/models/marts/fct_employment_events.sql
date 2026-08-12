-- Employment events: one row per hire and one per termination.
-- Unlike headcount (a snapshot measure that must never be summed
-- across dates), events are additive: counting them over any period
-- gives a correct answer, so no monthly rollup is needed here.

with employees as (

    select
        employees.*,
        person_map.person_key
    from {{ ref('stg_peoplecore__employees') }} as employees
    inner join {{ ref('int_peoplecore__person_map') }} as person_map
        using (employee_id)

),

hires as (

    select
        employee_id,
        person_key,
        hire_date as event_date,
        'hire' as event_type,
        department,
        employment_type,
        -- A person's second or later hire is a rehire. Only knowable
        -- because person_key links employment records the source
        -- system treats as unrelated.
        row_number() over (
            partition by person_key order by hire_date
        ) > 1 as is_rehire_event
    from employees

),

terminations as (

    select
        employee_id,
        person_key,
        termination_date as event_date,
        'termination' as event_type,
        department,
        employment_type,
        false as is_rehire_event
    from employees
    where termination_date is not null

),

all_events as (

    select * from hires
    union all
    select * from terminations

)

select
    employee_id,
    person_key,
    event_date,
    date_trunc(event_date, month) as event_month,
    event_type,
    department,
    employment_type,
    is_rehire_event
from all_events