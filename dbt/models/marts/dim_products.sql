-- marts/dim_products.sql
-- One row per product with category and brand.

{{ config(schema='marts', materialized='table') }}

SELECT
    product_id,
    category,
    brand
FROM {{ ref('stg_products') }}
