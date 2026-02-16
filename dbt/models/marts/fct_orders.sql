-- marts/fct_orders.sql
-- One row per order. Aggregates line items into revenue & item_count.
-- Includes date_id for dim_date join.

{{ config(schema='marts', materialized='table') }}

WITH order_agg AS (
    SELECT
        oi.order_id,
        SUM(oi.quantity)    AS item_count,
        SUM(oi.line_total)  AS revenue
    FROM {{ ref('stg_order_items') }} oi
    GROUP BY oi.order_id
)

SELECT
    o.order_id,
    o.user_id,
    o.order_ts,
    o.order_date,
    o.date_id,
    o.status,
    o.currency,
    COALESCE(a.item_count, 0)   AS item_count,
    COALESCE(a.revenue, 0)      AS revenue,
    CASE WHEN o.status = 'completed' THEN TRUE ELSE FALSE END AS is_completed
FROM {{ ref('stg_orders') }} o
LEFT JOIN order_agg a ON o.order_id = a.order_id
