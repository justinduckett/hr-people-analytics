with candidates as (

    select * from {{ ref('stg_talentflow__candidates') }}

),

applications as (

    select * from {{ ref('stg_talentflow__applications') }}

),

employees_keyed as (

    select
        employees.*,
        person_map.person_key
    from {{ ref('stg_peoplecore__employees') }} as employees
    inner join {{ ref('int_peoplecore__person_map') }} as person_map
        using (employee_id)

),

-- Rule 1: personal email match. Survives nicknames and name changes,
-- which is why it outranks name-based rules.
email_matches as (

    select
        candidates.candidate_id,
        employees_keyed.person_key,
        'personal_email' as match_rule
    from candidates
    inner join employees_keyed
        on candidates.personal_email = employees_keyed.personal_email
    where candidates.personal_email is not null

),

-- Rule 2: same full name AND a hired application whose start date
-- lands within 7 days of that employee's hire date. The date
-- alignment is the corroboration that makes name matching safe.
name_date_matches as (

    select
        candidates.candidate_id,
        employees_keyed.person_key,
        'name_and_start_date' as match_rule
    from candidates
    inner join applications
        on applications.candidate_id = candidates.candidate_id
        and applications.status = 'hired'
    inner join employees_keyed
        on  candidates.first_name = employees_keyed.first_name
        and candidates.last_name  = employees_keyed.last_name
        and abs(date_diff(
                employees_keyed.hire_date,
                applications.offer_start_date, day)) <= 7

),

direct_matches as (

    select * from email_matches
    union all
    select * from name_date_matches

),

-- Rule 3 (P5): a candidate sharing cleaned phone AND full name with
-- another candidate is the same human, and inherits any person_key
-- their twin earned through the direct rules.
phone_twin_matches as (

    select
        unmatched_twin.candidate_id,
        direct_matches.person_key,
        'phone_twin' as match_rule
    from candidates as unmatched_twin
    inner join candidates as matched_twin
        on  unmatched_twin.candidate_id != matched_twin.candidate_id
        and unmatched_twin.phone      = matched_twin.phone
        and unmatched_twin.first_name = matched_twin.first_name
        and unmatched_twin.last_name  = matched_twin.last_name
    inner join direct_matches
        on direct_matches.candidate_id = matched_twin.candidate_id

),

all_matches as (

    select * from direct_matches
    union all
    select * from phone_twin_matches

)

select
    candidates.candidate_id,
    min(all_matches.person_key)  as person_key,
    coalesce(
        string_agg(distinct all_matches.match_rule order by all_matches.match_rule),
        'no match (never hired)'
    )                            as match_basis,
    count(distinct all_matches.person_key) > 1
                                 as is_ambiguous
from candidates
left join all_matches
    using (candidate_id)
group by candidates.candidate_id