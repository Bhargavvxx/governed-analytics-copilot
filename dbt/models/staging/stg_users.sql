-- staging/stg_users.sql
-- Clean raw users: trim & normalise text fields.

{{ config(schema='staging') }}

SELECT
    user_id,
    signup_ts,
    CAST(signup_ts AS date)        AS signup_date,
    INITCAP(TRIM(country))         AS country,
    LOWER(TRIM(device))            AS device
FROM {{ source('raw', 'raw_users') }}
