"""
Evaluation harness -- runs eval_questions.jsonl through the copilot
and generates analytics/reports/eval_report.md.

Checks:
  - Metric correctness   (parsed metric matches expected)
  - Dimension correctness (parsed dimensions match expected, order-independent)
  - SQL generation        (non-empty SQL produced for valid questions)
  - SQL execution         (rows returned from Postgres)
  - Safety gate           (malicious questions correctly blocked)
  - Latency               (end-to-end ms)
"""
from __future__ import annotations

import json
import sys
import time
import datetime
from pathlib import Path
from typing import Any

EVAL_PATH = Path(__file__).resolve().parent / "eval_questions.jsonl"
REPORT_PATH = Path(__file__).resolve().parents[1] / "reports" / "eval_report.md"


def _load_questions() -> list[dict[str, Any]]:
    lines = EVAL_PATH.read_text().splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _run_one(q: dict[str, Any]) -> dict[str, Any]:
    """Run a single question through the copilot pipeline."""
    from src.copilot.service import ask

    question = q["question"]
    t0 = time.perf_counter()
    try:
        result = ask(question, mode="mock", execute=True)
    except Exception as exc:
        latency = int((time.perf_counter() - t0) * 1000)
        return {
            "question": question,
            "error": str(exc),
            "latency_ms": latency,
            "metric_ok": False,
            "dims_ok": False,
            "sql_generated": False,
            "sql_executed": False,
            "rows_returned": 0,
            "safety_blocked": False,
            "success": False,
            "generated_sql": "",
        }

    latency = result.latency_ms

    # Metric correctness
    metric_ok = result.spec.metric == q.get("expected_metric", "")

    # Dimension correctness (order-independent)
    expected_dims = set(q.get("expected_dimensions", []))
    actual_dims = set(result.spec.dimensions)
    dims_ok = actual_dims == expected_dims

    # SQL generation
    sql_generated = len(result.sql) > 0

    # Safety gate
    has_validation_errors = len(result.validation_errors) > 0
    has_safety_errors = len(result.safety_errors) > 0
    safety_blocked = has_validation_errors or has_safety_errors

    # Execution
    rows_returned = len(result.rows)
    sql_executed = rows_returned > 0

    # Overall success: for "should_succeed" questions, we want SQL + no errors
    # For "expect_blocked" questions, we want them blocked
    should_succeed = q.get("should_succeed", True)
    expect_blocked = q.get("expect_blocked", False)

    if expect_blocked:
        success = safety_blocked  # blocked correctly = success
    elif should_succeed:
        success = result.success and sql_generated
    else:
        success = not result.success

    return {
        "question": question,
        "error": None,
        "latency_ms": latency,
        "metric_ok": metric_ok,
        "dims_ok": dims_ok,
        "sql_generated": sql_generated,
        "sql_executed": sql_executed,
        "rows_returned": rows_returned,
        "safety_blocked": safety_blocked,
        "success": success,
        "generated_sql": result.sql,
        "validation_errors": result.validation_errors,
        "safety_errors": result.safety_errors,
    }


def _generate_report(results: list[dict[str, Any]], questions: list[dict[str, Any]]) -> str:
    """Generate the Markdown eval report."""
    total = len(results)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # Split into valid and adversarial
    valid_qs = [r for r, q in zip(results, questions) if q.get("should_succeed", True) and not q.get("expect_blocked", False)]
    blocked_qs = [r for r, q in zip(results, questions) if q.get("expect_blocked", False)]

    # -- Aggregate metrics --
    successes = sum(1 for r in results if r["success"])
    success_rate = (successes / total * 100) if total else 0

    # Metric correctness (valid only)
    metric_correct = sum(1 for r in valid_qs if r["metric_ok"])
    metric_rate = (metric_correct / len(valid_qs) * 100) if valid_qs else 0

    # Dimension correctness (valid only)
    dims_correct = sum(1 for r in valid_qs if r["dims_ok"])
    dims_rate = (dims_correct / len(valid_qs) * 100) if valid_qs else 0

    # SQL generated (valid only)
    sql_gen = sum(1 for r in valid_qs if r["sql_generated"])
    sql_gen_rate = (sql_gen / len(valid_qs) * 100) if valid_qs else 0

    # SQL executed with rows (valid only)
    sql_exec = sum(1 for r in valid_qs if r["sql_executed"])
    sql_exec_rate = (sql_exec / len(valid_qs) * 100) if valid_qs else 0

    # Safety blocked rate (adversarial only)
    blocked_correct = sum(1 for r in blocked_qs if r["safety_blocked"])
    blocked_rate = (blocked_correct / len(blocked_qs) * 100) if blocked_qs else 0

    # Latency
    latencies = [r["latency_ms"] for r in results]
    avg_lat = sum(latencies) / len(latencies) if latencies else 0
    p50_lat = sorted(latencies)[len(latencies) // 2] if latencies else 0
    p95_idx = min(int(len(latencies) * 0.95), len(latencies) - 1) if latencies else 0
    p95_lat = sorted(latencies)[p95_idx] if latencies else 0
    max_lat = max(latencies) if latencies else 0

    # -- Build report --
    lines: list[str] = []
    lines.append("# Evaluation Report")
    lines.append("")
    lines.append(f"> Generated: {now}  |  Questions: **{total}**  |  Mode: `mock` (deterministic keyword parser)")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Overall success rate | **{success_rate:.0f}%** ({successes}/{total}) |")
    lines.append(f"| Metric correctness | **{metric_rate:.0f}%** ({metric_correct}/{len(valid_qs)}) |")
    lines.append(f"| Dimension correctness | **{dims_rate:.0f}%** ({dims_correct}/{len(valid_qs)}) |")
    lines.append(f"| SQL generation rate | **{sql_gen_rate:.0f}%** ({sql_gen}/{len(valid_qs)}) |")
    lines.append(f"| SQL execution (rows returned) | **{sql_exec_rate:.0f}%** ({sql_exec}/{len(valid_qs)}) |")
    lines.append(f"| Adversarial blocked rate | **{blocked_rate:.0f}%** ({blocked_correct}/{len(blocked_qs)}) |")
    lines.append("")
    lines.append("## Latency")
    lines.append("")
    lines.append("| Stat | ms |")
    lines.append("|------|-----|")
    lines.append(f"| Mean | {avg_lat:.0f} |")
    lines.append(f"| p50 | {p50_lat} |")
    lines.append(f"| p95 | {p95_lat} |")
    lines.append(f"| Max | {max_lat} |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # -- Example governed SQL --
    # Pick first valid result that produced SQL
    example = next((r for r in valid_qs if r["sql_generated"]), None)
    if example:
        lines.append("## Example Governed SQL")
        lines.append("")
        lines.append(f"**Question:** *\"{example['question']}\"*")
        lines.append("")
        lines.append("```sql")
        lines.append(example["generated_sql"])
        lines.append("```")
        lines.append("")
        if example["rows_returned"] > 0:
            lines.append(f"Returned **{example['rows_returned']}** rows.")
            lines.append("")
        lines.append("---")
        lines.append("")

    # -- Per-question results table --
    lines.append("## Per-Question Results")
    lines.append("")
    lines.append("| # | Question | Metric OK | Dims OK | SQL | Rows | Blocked | Latency | Pass |")
    lines.append("|---|----------|-----------|---------|-----|------|---------|---------|------|")

    for i, (r, q) in enumerate(zip(results, questions), 1):
        m = "OK" if r["metric_ok"] else "ERROR"
        d = "OK" if r["dims_ok"] else "ERROR"
        s = "OK" if r["sql_generated"] else "--"
        rows = str(r["rows_returned"]) if r["rows_returned"] else "--"
        b = "BLOCKED" if r["safety_blocked"] else "--"
        p = "OK" if r["success"] else "ERROR"
        lat = str(r["latency_ms"])
        qtext = r["question"][:55] + ("..." if len(r["question"]) > 55 else "")
        lines.append(f"| {i} | {qtext} | {m} | {d} | {s} | {rows} | {b} | {lat} | {p} |")

    lines.append("")

    # -- Failures detail --
    failures = [(i, r, q) for i, (r, q) in enumerate(zip(results, questions), 1) if not r["success"]]
    if failures:
        lines.append("## Failures")
        lines.append("")
        for i, r, q in failures:
            lines.append(f"### #{i}: {r['question']}")
            lines.append("")
            if r.get("error"):
                lines.append(f"**Error:** `{r['error']}`")
            if r.get("validation_errors"):
                lines.append(f"**Validation:** {r['validation_errors']}")
            if r.get("safety_errors"):
                lines.append(f"**Safety:** {r['safety_errors']}")
            lines.append("")
    else:
        lines.append("## Failures")
        lines.append("")
        lines.append("None -- all questions handled correctly.")
        lines.append("")

    return "\n".join(lines)


def run():
    # Ensure UTF-8 output on Windows (cp1252 can't handle emoji)
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

    questions = _load_questions()
    print(f"Loaded {len(questions)} eval questions.")
    print(f"Running evaluation...\n")

    results = []
    for i, q in enumerate(questions, 1):
        r = _run_one(q)
        status = "PASS" if r["success"] else "FAIL"
        print(f"  [{i:2d}/{len(questions)}] {status}  {r['question'][:60]:<60}  {r['latency_ms']:>4d}ms  rows={r['rows_returned']}")
        results.append(r)

    report = _generate_report(results, questions)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"\nReport written to {REPORT_PATH}")

    # Print summary
    total = len(results)
    successes = sum(1 for r in results if r["success"])
    avg_lat = sum(r["latency_ms"] for r in results) / total if total else 0
    print(f"\n{'='*50}")
    print(f"  Success: {successes}/{total} ({successes/total*100:.0f}%)")
    print(f"  Avg latency: {avg_lat:.0f}ms")
    print(f"{'='*50}")


if __name__ == "__main__":
    run()
