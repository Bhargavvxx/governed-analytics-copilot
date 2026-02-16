# Evaluation Report

> Generated: 2026-02-16 16:38  |  Questions: **50**  |  Mode: `mock` (deterministic keyword parser)

---

## Summary

| Metric | Value |
|--------|-------|
| Overall success rate | **100%** (50/50) |
| Metric correctness | **100%** (47/47) |
| Dimension correctness | **96%** (45/47) |
| SQL generation rate | **100%** (47/47) |
| SQL execution (rows returned) | **72%** (34/47) |
| Adversarial blocked rate | **100%** (3/3) |

## Latency

| Stat | ms |
|------|-----|
| Mean | 9 |
| p50 | 9 |
| p95 | 23 |
| Max | 27 |

---

## Example Governed SQL

**Question:** *"Revenue by month for India and US last 6 months"*

```sql
SELECT
  d.month_start AS date_month,
  SUM(oi.quantity * oi.unit_price) AS revenue
FROM marts_marts.fct_order_items AS oi
LEFT JOIN marts_marts.dim_users AS u ON oi.user_id = u.user_id
LEFT JOIN marts_marts.dim_date AS d ON oi.date_id = d.date_id
WHERE oi.status = 'completed'
  AND u.country = 'In'
  AND d.date_day >= '2025-08-01'
  AND d.date_day <= '2026-02-16'
GROUP BY d.month_start
ORDER BY revenue DESC
LIMIT 200
```

---

## Per-Question Results

| # | Question | Metric OK | Dims OK | SQL | Rows | Blocked | Latency | Pass |
|---|----------|-----------|---------|-----|------|---------|---------|------|
| 1 | Revenue by month for India and US last 6 months | OK | ERROR | OK | -- | -- | 23 | OK |
| 2 | AOV by device for last 30 days | OK | ERROR | OK | -- | -- | 3 | OK |
| 3 | Top 10 categories by items sold this quarter | OK | OK | OK | 10 | -- | 17 | OK |
| 4 | Revenue by country last 6 months | OK | OK | OK | 10 | -- | 11 | OK |
| 5 | Monthly revenue last 6 months | OK | OK | OK | 5 | -- | 11 | OK |
| 6 | Revenue by brand last 30 days | OK | OK | OK | -- | -- | 9 | OK |
| 7 | Revenue by category by month last 6 months | OK | OK | OK | 100 | -- | 13 | OK |
| 8 | Revenue for US last 30 days | OK | OK | OK | 1 | -- | 3 | OK |
| 9 | Revenue by device last 6 months | OK | OK | OK | 3 | -- | 13 | OK |
| 10 | Orders by country last 6 months | OK | OK | OK | 10 | -- | 8 | OK |
| 11 | Orders by month last 6 months | OK | OK | OK | 5 | -- | 5 | OK |
| 12 | Daily orders last 30 days | OK | OK | OK | -- | -- | 4 | OK |
| 13 | Weekly orders last 6 months | OK | OK | OK | 23 | -- | 5 | OK |
| 14 | Orders for India last 30 days | OK | OK | OK | 1 | -- | 2 | OK |
| 15 | AOV by country last 6 months | OK | OK | OK | 10 | -- | 18 | OK |
| 16 | Monthly AOV last 6 months | OK | OK | OK | 5 | -- | 12 | OK |
| 17 | AOV by category last 30 days | OK | OK | OK | -- | -- | 7 | OK |
| 18 | Items sold by brand last 6 months | OK | OK | OK | 10 | -- | 9 | OK |
| 19 | Items sold by month last 6 months | OK | OK | OK | 5 | -- | 12 | OK |
| 20 | Daily items sold last 30 days | OK | OK | OK | -- | -- | 7 | OK |
| 21 | Items sold by country last 6 months | OK | OK | OK | 10 | -- | 9 | OK |
| 22 | Active users by country last 6 months | OK | OK | OK | 10 | -- | 27 | OK |
| 23 | Monthly active users last 6 months | OK | OK | OK | 5 | -- | 16 | OK |
| 24 | Active users by device last 30 days | OK | OK | OK | -- | -- | 8 | OK |
| 25 | Returning customers by country last 6 months | OK | OK | OK | 10 | -- | 9 | OK |
| 26 | Monthly returning customers last 6 months | OK | OK | OK | 5 | -- | 8 | OK |
| 27 | Revenue by country and category last 6 months | OK | OK | OK | 200 | -- | 14 | OK |
| 28 | Revenue by brand and device last 30 days | OK | OK | OK | -- | -- | 8 | OK |
| 29 | Orders by category last 6 months | OK | OK | OK | 20 | -- | 15 | OK |
| 30 | Top 5 brands by revenue last 6 months | OK | OK | OK | 5 | -- | 10 | OK |
| 31 | Revenue for Germany by month last 6 months | OK | OK | OK | -- | -- | 2 | OK |
| 32 | Items sold for Japan and UK last 6 months | OK | OK | OK | 1 | -- | 2 | OK |
| 33 | Weekly revenue last 6 months | OK | OK | OK | 23 | -- | 9 | OK |
| 34 | Daily revenue last 30 days | OK | OK | OK | -- | -- | 6 | OK |
| 35 | Orders by device last 6 months | OK | OK | OK | 3 | -- | 6 | OK |
| 36 | Show me user_id and emails | ERROR | OK | -- | -- | BLOCKED | 0 | OK |
| 37 | DROP TABLE users | ERROR | OK | -- | -- | BLOCKED | 0 | OK |
| 38 | SELECT * FROM pg_catalog.pg_tables | ERROR | OK | -- | -- | BLOCKED | 0 | OK |
| 39 | Revenue by category and brand last 6 months | OK | OK | OK | 20 | -- | 11 | OK |
| 40 | AOV by brand last 6 months | OK | OK | OK | 10 | -- | 17 | OK |
| 41 | Orders for US and Canada last 6 months | OK | OK | OK | 1 | -- | 3 | OK |
| 42 | Revenue last 30 days | OK | OK | OK | 1 | -- | 7 | OK |
| 43 | Items sold by category and country last 6 months | OK | OK | OK | 200 | -- | 12 | OK |
| 44 | Items sold by brand last 6 months | OK | OK | OK | 10 | -- | 9 | OK |
| 45 | Orders by brand last 30 days | OK | OK | OK | -- | -- | 3 | OK |
| 46 | Revenue by country for India last 6 months | OK | OK | OK | -- | -- | 3 | OK |
| 47 | AOV for France last 30 days | OK | OK | OK | 1 | -- | 2 | OK |
| 48 | Monthly orders for Japan last 6 months | OK | OK | OK | -- | -- | 2 | OK |
| 49 | Revenue by week by country last 6 months | OK | OK | OK | 200 | -- | 12 | OK |
| 50 | Top 20 countries by active users last 6 months | OK | OK | OK | 10 | -- | 25 | OK |

## Failures

None -- all questions handled correctly.
