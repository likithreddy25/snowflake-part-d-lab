{% snapshot snap_prescriber %}

{{
  config(
    target_schema='marts',
    unique_key='prescriber_key',
    strategy='check',
    check_cols=['provider_org_name', 'provider_first_name', 'provider_city', 'prescriber_type']
  )
}}

-- Type 2 slowly changing dimension. Each run compares the tracked columns with the stored
-- version. If any changed, dbt closes the old row (dbt_valid_to) and inserts a new one.
SELECT * FROM {{ ref('dim_prescriber') }}

{% endsnapshot %}
