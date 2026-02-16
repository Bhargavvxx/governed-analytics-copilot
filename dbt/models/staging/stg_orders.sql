-- staging/stg_orders.sql
-- Clean raw orders: cast types, derive date_id for dim_date join.

{{ config(schema='staging') }}

SELECT
    order_id,
    user_id,
    order_ts,
    CAST(order_ts AS date)                   AS order_date,
    TO_CHAR(order_ts, 'YYYYMMDD')::INT       AS date_id,
    LOWER(TRIM(status))                      AS status,
    UPPER(TRIM(currency))                    AS currency
FROM {{ source('raw', 'raw_orders') }}
