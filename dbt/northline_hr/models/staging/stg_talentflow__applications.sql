with source as (

    select * from {{ source('hr_raw', 'talentflow_candidates') }}

)

select
    app.application_id,
    source.candidate_id,
    trim(app.job_title)                as job_title,
    trim(app.department)               as department,
    cast(app.applied_at as date)       as applied_at,
    app.status,
    cast(app.offer.accepted_at as date)  as offer_accepted_at,
    cast(app.offer.start_date as date)   as offer_start_date
from source,
    unnest(source.applications) as app