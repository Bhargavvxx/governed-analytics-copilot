# Evaluation Report

> Generated: 2026-02-16 15:40  |  Questions: **50**  |  Mode: `mock` (deterministic keyword parser)

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
| Mean | 6 |
| p50 | 4 |
| p95 | 13 |
| Max | 122 |

---

## Example Governed SQL

**Question:** *"Revenue by month for India and US last 6 months"*

```sql
SELECT
  d.month_start AS date_month,
  SUM(oi.quantity * oi.unit_price) AS revenue
FROM marts_marts.fct_order_items AS oi
LEFT JOIN marts_marts.dim_date AS d ON oi.date_id = d.date_id
LEFT JOIN marts_marts.dim_users AS u ON oi.user_id = u.user_id
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
| 1 | Revenue by month for India and US last 6 months | Done | ❌ | Done | — | — | 13 | Done |
| 2 | AOV by device for last 30 days | Done | ❌ | Done | — | — | 3 | Done |
| 3 | Top 10 categories by items sold this quarter | Done | Done | Done | 10 | — | 7 | Done |
| 4 | Revenue by country last 6 months | Done | Done | Done | 10 | — | 6 | Done |
| 5 | Monthly revenue last 6 months | Done | Done | Done | 5 | — | 6 | Done |
| 6 | Revenue by brand last 30 days | Done | Done | Done | — | — | 4 | Done |
| 7 | Revenue by category by month last 6 months | Done | Done | Done | 100 | — | 6 | Done |
| 8 | Revenue for US last 30 days | Done | Done | Done | 1 | — | 1 | Done |
| 9 | Revenue by device last 6 months | Done | Done | Done | 3 | — | 5 | Done |
| 10 | Orders by country last 6 months | Done | Done | Done | 10 | — | 3 | Done |
| 11 | Orders by month last 6 months | Done | Done | Done | 5 | — | 2 | Done |
| 12 | Daily orders last 30 days | Done | Done | Done | — | — | 1 | Done |
| 13 | Weekly orders last 6 months | Done | Done | Done | 23 | — | 2 | Done |
| 14 | Orders for India last 30 days | Done | Done | Done | 1 | — | 1 | Done |
| 15 | AOV by country last 6 months | Done | Done | Done | 10 | — | 8 | Done |
| 16 | Monthly AOV last 6 months | Done | Done | Done | 5 | — | 6 | Done |
| 17 | AOV by category last 30 days | Done | Done | Done | — | — | 3 | Done |
| 18 | Items sold by brand last 6 months | Done | Done | Done | 10 | — | 4 | Done |
| 19 | Items sold by month last 6 months | Done | Done | Done | 5 | — | 4 | Done |
| 20 | Daily items sold last 30 days | Done | Done | Done | — | — | 3 | Done |
| 21 | Items sold by country last 6 months | Done | Done | Done | 10 | — | 5 | Done |
| 22 | Active users by country last 6 months | Done | Done | Done | 10 | — | 13 | Done |
| 23 | Monthly active users last 6 months | Done | Done | Done | 5 | — | 8 | Done |
| 24 | Active users by device last 30 days | Done | Done | Done | — | — | 4 | Done |
| 25 | Returning customers by country last 6 months | Done | Done | Done | 10 | — | 4 | Done |
| 26 | Monthly returning customers last 6 months | Done | Done | Done | 5 | — | 3 | Done |
| 27 | Revenue by country and category last 6 months | Done | Done | Done | 200 | — | 6 | Done |
| 28 | Revenue by brand and device last 30 days | Done | Done | Done | — | — | 3 | Done |
| 29 | Orders by category last 6 months | Done | Done | Done | 20 | — | 7 | Done |
| 30 | Top 5 brands by revenue last 6 months | Done | Done | Done | 5 | — | 5 | Done |
| 31 | Revenue for Germany by month last 6 months | Done | Done | Done | — | — | 1 | Done |
| 32 | Items sold for Japan and UK last 6 months | Done | Done | Done | 1 | — | 1 | Done |
| 33 | Weekly revenue last 6 months | Done | Done | Done | 23 | — | 4 | Done |
| 34 | Daily revenue last 30 days | Done | Done | Done | — | — | 3 | Done |
| 35 | Orders by device last 6 months | Done | Done | Done | 3 | — | 2 | Done |
| 36 | Show me user_id and emails | ❌ | Done | — | — | Blocked | 0 | Done |
| 37 | DROP TABLE users | ❌ | Done | — | — | Blocked | 0 | Done |
| 38 | SELECT * FROM pg_catalog.pg_tables | ❌ | Done | — | — | Blocked | 0 | Done |
| 39 | Revenue by category and brand last 6 months | Done | Done | Done | 20 | — | 5 | Done |
| 40 | AOV by brand last 6 months | Done | Done | Done | 10 | — | 8 | Done |
| 41 | Orders for US and Canada last 6 months | Done | Done | Done | 1 | — | 1 | Done |
| 42 | Revenue last 30 days | Done | Done | Done | 1 | — | 3 | Done |
| 43 | Items sold by category and country last 6 months | Done | Done | Done | 200 | — | 5 | Done |
| 44 | Active users by brand last 6 months | Done | Done | Done | 11 | — | 122 | Done |
| 45 | Orders by brand last 30 days | Done | Done | Done | — | — | 2 | Done |
| 46 | Revenue by country for India last 6 months | Done | Done | Done | — | — | 1 | Done |
| 47 | AOV for France last 30 days | Done | Done | Done | 1 | — | 1 | Done |
| 48 | Monthly orders for Japan last 6 months | Done | Done | Done | — | — | 1 | Done |
| 49 | Revenue by week by country last 6 months | Done | Done | Done | 200 | — | 6 | Done |
| 50 | Top 20 countries by active users last 6 months | Done | Done | Done | 10 | — | 12 | Done |

## Failures

None — all questions handled correctly.
