{% snapshot peoplecore_employees_snapshot %}

{{
    config(
      unique_key='employee_id',
      strategy='check',
      check_cols=[
          'department',
          'job_title',
          'employment_type',
          'salary_band',
          'status',
          'termination_date',
      ],
    )
}}

select * from {{ ref('stg_peoplecore__employees') }}

{% endsnapshot %}