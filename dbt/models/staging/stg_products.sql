-- staging/stg_products.sql
-- Clean raw products: trim text fields.

{{ config(schema='staging') }}

SELECT
    product_id,
    TRIM(category)   AS category,
    TRIM(brand)      AS brand
FROM {{ source('raw', 'raw_products') }}
