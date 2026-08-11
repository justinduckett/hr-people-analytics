-- Current headcount: the single most recent daily snapshot, one row
-- per department per employment type. Powers all "as of today" tiles
-- so they never sum across dates.

with daily as (

    select * from {{ ref('fct_headcount_daily') }}

),

latest as (

    select max(date_day) as date_day from daily

)

select
    daily.department,
    daily.employment_type,
    daily.headcount
from daily
inner join latest
    using (date_day)