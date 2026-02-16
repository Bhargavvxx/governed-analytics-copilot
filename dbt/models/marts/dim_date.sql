-- marts/dim_date.sql
-- Date spine from 2023-01-01 to 2026-12-31.
-- Provides day / week / month grains for all time-series queries.

{{ config(schema='marts', materialized='table') }}

WITH date_spine AS (
    SELECT
        generate_series(
            '2023-01-01'::date,
            '2026-12-31'::date,
            '1 day'::interval
        )::date AS date_day
)

SELECT
    TO_CHAR(date_day, 'YYYYMMDD')::INT     AS date_id,
    date_day,
    EXTRACT(DOW FROM date_day)::INT         AS day_of_week,      -- 0=Sun
    EXTRACT(DAY FROM date_day)::INT         AS day_of_month,
    EXTRACT(DOY FROM date_day)::INT         AS day_of_year,
    DATE_TRUNC('week', date_day)::date      AS week_start,
    DATE_TRUNC('month', date_day)::date     AS month_start,
    TO_CHAR(date_day, 'YYYY-MM')            AS year_month,
    EXTRACT(MONTH FROM date_day)::INT       AS month_num,
    TO_CHAR(date_day, 'Month')              AS month_name,
    DATE_TRUNC('quarter', date_day)::date   AS quarter_start,
    EXTRACT(QUARTER FROM date_day)::INT     AS quarter_num,
    EXTRACT(YEAR FROM date_day)::INT        AS year_num,
    CASE WHEN EXTRACT(DOW FROM date_day) IN (0, 6) THEN TRUE ELSE FALSE END AS is_weekend
FROM date_spine
