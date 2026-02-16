-- staging/stg_order_items.sql
-- Clean raw order items: cast, derive line_total.

{{ config(schema='staging') }}

SELECT
    order_id,
    product_id,
    quantity,
    unit_price,
    (quantity * unit_price)  AS line_total
FROM {{ source('raw', 'raw_order_items') }}
