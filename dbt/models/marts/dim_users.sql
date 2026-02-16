-- marts/dim_users.sql
-- One row per user with signup attributes.

{{ config(schema='marts', materialized='table') }}

SELECT
    user_id,
    signup_ts,
    signup_date,
    country,
    device
FROM {{ ref('stg_users') }}
