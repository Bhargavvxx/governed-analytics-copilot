-- staging/stg_sessions.sql
-- Clean raw sessions: normalise text fields.

{{ config(schema='staging') }}

SELECT
    session_id,
    user_id,
    session_ts,
    CAST(session_ts AS date)        AS session_date,
    LOWER(TRIM(device))             AS device,
    INITCAP(TRIM(country))          AS country
FROM {{ source('raw', 'raw_sessions') }}
