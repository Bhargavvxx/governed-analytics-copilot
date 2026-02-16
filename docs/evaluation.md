# Evaluation Methodology

## Eval set

- Located at `analytics/eval/eval_questions.jsonl`
- Each line is a JSON object with: `question`, `expected_metric`, `expected_grain`, `expected_dimensions`, `expected_filters`
- Target: 50+ questions covering all 7 metrics and all dimensions

## Metrics computed

| Metric | Definition |
|--------|-----------|
| Execution success rate | % of questions that produce valid SQL and return rows |
| Metric correctness | % where generated SQL uses the correct semantic definition |
| Forbidden access rate | % where blocked columns/tables appear in generated SQL |
| Avg latency | Mean end-to-end latency (ms) |

## Running

```bash
python -m analytics.eval.run_eval
```

Report output: `analytics/reports/eval_report.md`
