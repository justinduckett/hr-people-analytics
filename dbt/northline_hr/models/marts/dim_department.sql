-- One row per standardized department, with the attributes an HR
-- team would slice by. Built from the department_mapping seed so the
-- department list has a single source of truth: the same seed that
-- standardizes the source system's free-text spellings.
--
-- Note on usage: fct_employment_events carries department_name
-- directly rather than a surrogate key, so joins to this dimension
-- are on the name. No surrogate key is defined: the dimension is
-- Type 1 with a small, stable set of rows, and nothing joins on an
-- integer key.

with departments as (

    select distinct department
    from {{ ref('department_mapping') }}

),

enriched as (

    select
        department as department_name,

        -- Division groups departments the way leadership reports on
        -- them, so turnover can be compared across the business
        -- without knowing which departments sit where.
        case
            when department in ('Retail Operations', 'Merchandising')
                then 'Stores'
            when department = 'Distribution'
                then 'Supply Chain'
            else 'Head Office'
        end as division,

        -- Frontline departments hire seasonally and churn faster.
        -- This flag encodes that distinction once, rather than
        -- rebuilding the department list in every analysis.
        department in ('Retail Operations', 'Distribution')
            as is_frontline

    from departments

)

select
    department_name,
    division,
    is_frontline
from enriched