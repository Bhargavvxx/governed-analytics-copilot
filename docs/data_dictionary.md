# Data Dictionary

## Raw tables (schema: `raw`)

| Table | Column | Type | Description |
|-------|--------|------|-------------|
| raw_orders | order_id | BIGINT | PK |
| raw_orders | user_id | BIGINT | FK to raw_users |
| raw_orders | order_ts | TIMESTAMP | Order timestamp |
| raw_orders | status | VARCHAR(20) | completed / cancelled / pending |
| raw_orders | currency | VARCHAR(3) | ISO currency code |
| raw_order_items | order_id | BIGINT | FK to raw_orders |
| raw_order_items | product_id | BIGINT | FK to raw_products |
| raw_order_items | quantity | INT | Units purchased |
| raw_order_items | unit_price | NUMERIC(12,2) | Price per unit |
| raw_users | user_id | BIGINT | PK |
| raw_users | signup_ts | TIMESTAMP | Registration time |
| raw_users | country | VARCHAR(50) | User country |
| raw_users | device | VARCHAR(20) | mobile / desktop / tablet |
| raw_products | product_id | BIGINT | PK |
| raw_products | category | VARCHAR(100) | Product category |
| raw_products | brand | VARCHAR(100) | Product brand |
| raw_sessions | session_id | BIGINT | PK |
| raw_sessions | user_id | BIGINT | FK to raw_users |
| raw_sessions | session_ts | TIMESTAMP | Session start |
| raw_sessions | device | VARCHAR(20) | Device type |
| raw_sessions | country | VARCHAR(50) | Country |

## Mart tables (schema: `marts`) — built by dbt

| Model | Description |
|-------|-------------|
| fct_orders | One row per order; includes revenue, item_count; completed flags |
| fct_order_items | Line-level items joined with order status |
| dim_users | User attributes |
| dim_products | Product attributes |
| dim_date | Date spine for time grains |

## Metrics (governed)

See `semantic_layer/semantic_model.yml` for canonical definitions.
