-- marts/fct_order_items.sql
-- Line-level items joined with order header (status, dates, user).
-- This is the primary table for revenue / items_sold metrics.

{{ config(schema='marts', materialized='table') }}

SELECT
    oi.order_id,
    oi.product_id,
    oi.quantity,
    oi.unit_price,
    oi.line_total,
    o.user_id,
    o.order_ts,
    o.order_date,
    o.date_id,
    o.status,
    o.currency,
    CASE WHEN o.status = 'completed' THEN TRUE ELSE FALSE END AS is_completed
FROM {{ ref('stg_order_items') }} oi
INNER JOIN {{ ref('stg_orders') }} o ON oi.order_id = o.order_id
