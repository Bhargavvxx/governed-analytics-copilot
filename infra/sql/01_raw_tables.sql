-- 01_raw_tables.sql
-- Raw e-commerce tables populated by the seed script.

CREATE TABLE IF NOT EXISTS raw.raw_orders (
    order_id    BIGINT PRIMARY KEY,
    user_id     BIGINT NOT NULL,
    order_ts    TIMESTAMP NOT NULL,
    status      VARCHAR(20) NOT NULL,   -- completed | cancelled | pending
    currency    VARCHAR(3) NOT NULL DEFAULT 'USD'
);

CREATE TABLE IF NOT EXISTS raw.raw_order_items (
    order_id    BIGINT NOT NULL REFERENCES raw.raw_orders(order_id),
    product_id  BIGINT NOT NULL,
    quantity    INT NOT NULL,
    unit_price  NUMERIC(12,2) NOT NULL,
    PRIMARY KEY (order_id, product_id)
);

CREATE TABLE IF NOT EXISTS raw.raw_users (
    user_id     BIGINT PRIMARY KEY,
    signup_ts   TIMESTAMP NOT NULL,
    country     VARCHAR(50) NOT NULL,
    device      VARCHAR(20) NOT NULL    -- mobile | desktop | tablet
);

CREATE TABLE IF NOT EXISTS raw.raw_products (
    product_id  BIGINT PRIMARY KEY,
    category    VARCHAR(100) NOT NULL,
    brand       VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS raw.raw_sessions (
    session_id  BIGINT PRIMARY KEY,
    user_id     BIGINT NOT NULL,
    session_ts  TIMESTAMP NOT NULL,
    device      VARCHAR(20) NOT NULL,
    country     VARCHAR(50) NOT NULL
);
