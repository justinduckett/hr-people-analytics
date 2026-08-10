select
    day                                   as date_day,
    extract(year from day)                as year,
    extract(month from day)               as month,
    format_date('%Y-%m', day)             as year_month,
    date_trunc(day, month)                as month_start_date,
    format_date('%A', day)                as day_name,
    extract(dayofweek from day) in (1, 7) as is_weekend
from unnest(generate_date_array('2015-01-01', current_date())) as day