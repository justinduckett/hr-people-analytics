-- Monthly headcount snapshot: one row per month per department per
-- employment type, measuring headcount on the last day of each month.
-- Sampling a single day per month gives each month exactly one
-- unambiguous headcount, instead of asking Looker to aggregate ~30
-- daily snapshots (which double-counts or guesses).

with daily as (

    select * from {{ ref('fct_headcount_daily') }}

),

month_end_dates as (

    -- the latest date we actually have data for within each month
    select max(date_day) as date_day
    from daily
    group by date_trunc(date_day, month)

)

select
    daily.date_day,
    date_trunc(daily.date_day, month) as month_start_date,
    daily.department,
    daily.employment_type,
    daily.headcount
from daily
inner join month_end_dates
    using (date_day)