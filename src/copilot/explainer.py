"""
LLM-based explanation layer.

Generates human-readable explanations for:
  - Why a query was blocked (validation / safety / RBAC / cost errors)
  - How to fix a rejected query
  - What a successful query does in plain language

Works in both ``mock`` mode (template-based, no API key needed) and
``llm`` mode (calls the configured LLM provider for richer output).
"""
from __future__ import annotations

from typing import Any

from src.core.logging import get_logger

logger = get_logger(__name__)


# ── Template-based explanations (mock / offline) ────────


_BLOCK_TEMPLATES: dict[str, str] = {
    "unknown metric": (
        "The metric you requested is not defined in the semantic layer. "
        "Check the catalog sidebar for available metrics and try again."
    ),
    "unknown dimension": (
        "One or more dimensions you used are not recognised. "
        "Open the catalog to see valid dimension names."
    ),
    "not allowed": (
        "The dimension you requested is not permitted for this metric. "
        "Each metric only supports specific breakdowns — check the catalog."
    ),
    "derived": (
        "This metric is a *derived* (composite) metric and cannot be queried directly. "
        "Try querying its component metrics individually instead."
    ),
    "blocked column": (
        "The generated SQL tried to expose a blocked column (e.g. user_id). "
        "Governance rules prevent PII from appearing in query results."
    ),
    "dangerous": (
        "The query contains a dangerous SQL keyword (DROP, ALTER, etc.). "
        "Only read-only SELECT queries are allowed."
    ),
    "role": (
        "Your role does not have access to the requested metric or dimension. "
        "Contact your administrator to request elevated access."
    ),
    "cost": (
        "The estimated query cost is too high. Try reducing the number of "
        "dimensions, adding a time-range filter, or lowering the row limit."
    ),
    "injection": (
        "Your question appears to contain SQL injection patterns. "
        "Please rephrase using plain business language."
    ),
    "pii": (
        "Your question requests personally identifiable information, "
        "which is blocked by governance rules."
    ),
}


def _match_template(error_msg: str) -> str:
    """Find the best template for a given error message."""
    lower = error_msg.lower()
    for key, template in _BLOCK_TEMPLATES.items():
        if key in lower:
            return template
    return (
        "The query was blocked due to a governance rule. "
        "Review the error details and adjust your question accordingly."
    )


def explain_errors_mock(
    question: str,
    validation_errors: list[str],
    safety_errors: list[str],
    cost_warnings: list[str] | None = None,
    rbac_errors: list[str] | None = None,
) -> str:
    """Generate a human-readable explanation using templates (no LLM call).

    Returns a Markdown-formatted explanation string.
    """
    sections: list[str] = []

    all_errors = (
        validation_errors
        + safety_errors
        + (cost_warnings or [])
        + (rbac_errors or [])
    )

    if not all_errors:
        return (
            "Your query executed successfully! "
            "The copilot translated your question into governed SQL, "
            "validated it against the semantic layer, and returned the results."
        )

    sections.append("**Why was your query blocked?**\n")

    for i, err in enumerate(all_errors, 1):
        explanation = _match_template(err)
        sections.append(f"{i}. **{err}**\n   → {explanation}\n")

    sections.append("\n**How to fix it:**\n")
    suggestions = _generate_fix_suggestions(validation_errors, safety_errors, cost_warnings, rbac_errors)
    for s in suggestions:
        sections.append(f"- {s}")

    return "\n".join(sections)


def _generate_fix_suggestions(
    v_errors: list[str],
    s_errors: list[str],
    cost_warnings: list[str] | None = None,
    rbac_errors: list[str] | None = None,
) -> list[str]:
    """Generate targeted fix suggestions based on error categories."""
    suggestions: list[str] = []
    all_text = " ".join(v_errors + s_errors + (cost_warnings or []) + (rbac_errors or [])).lower()

    if "unknown metric" in all_text:
        suggestions.append("Check the **Catalog** sidebar for the list of available metrics.")
    if "unknown dimension" in all_text or "not allowed" in all_text:
        suggestions.append("Verify that the dimension is supported for your chosen metric.")
    if "derived" in all_text:
        suggestions.append("Query the component metrics separately instead of the derived one.")
    if "blocked column" in all_text:
        suggestions.append("Remove references to PII columns like `user_id` or `order_id`.")
    if "dangerous" in all_text or "injection" in all_text:
        suggestions.append("Rephrase your question using plain business language, without SQL keywords.")
    if "cost" in all_text or "expensive" in all_text:
        suggestions.append("Add a time-range filter (e.g. 'last 3 months') to narrow the dataset.")
        suggestions.append("Reduce the number of dimensions or lower the row limit.")
    if "role" in all_text:
        suggestions.append("Ask your administrator to grant access, or choose a different metric.")
    if "pii" in all_text or "personally identifiable" in all_text:
        suggestions.append("Avoid requesting personal data like emails, passwords, or addresses.")

    if not suggestions:
        suggestions.append("Try rephrasing your question with simpler terms.")
        suggestions.append("Check the metric catalog for supported breakdowns.")

    return suggestions


def explain_errors_llm(
    question: str,
    validation_errors: list[str],
    safety_errors: list[str],
    cost_warnings: list[str] | None = None,
    rbac_errors: list[str] | None = None,
) -> str:
    """Generate explanation using the configured LLM provider.

    Falls back to mock if the LLM call fails.
    """
    from src.copilot.llm_client import call_llm

    all_errors = (
        validation_errors
        + safety_errors
        + (cost_warnings or [])
        + (rbac_errors or [])
    )

    if not all_errors:
        return explain_errors_mock(question, validation_errors, safety_errors, cost_warnings, rbac_errors)

    prompt = (
        "You are a helpful analytics assistant. A user asked the following business question "
        "but it was blocked by governance rules.\n\n"
        f"**User question:** {question}\n\n"
        f"**Errors:**\n" + "\n".join(f"- {e}" for e in all_errors) + "\n\n"
        "Please explain in 2-3 sentences:\n"
        "1. WHY the query was blocked (in simple terms)\n"
        "2. HOW the user can fix their question to make it work\n\n"
        "Be concise and helpful. Use plain language."
    )

    try:
        response = call_llm(prompt)
        return response
    except Exception as exc:
        logger.warning("LLM explanation failed, falling back to mock: %s", exc)
        return explain_errors_mock(question, validation_errors, safety_errors, cost_warnings, rbac_errors)


def explain_errors(
    question: str,
    validation_errors: list[str],
    safety_errors: list[str],
    cost_warnings: list[str] | None = None,
    rbac_errors: list[str] | None = None,
    mode: str = "mock",
) -> str:
    """Public API — dispatches to mock or LLM-based explanation.

    Parameters
    ----------
    question : str
        The original user question.
    validation_errors, safety_errors, cost_warnings, rbac_errors : list[str]
        Error lists from the pipeline.
    mode : str
        ``"mock"`` for template-based, anything else for LLM-based.
    """
    if mode == "mock":
        return explain_errors_mock(question, validation_errors, safety_errors, cost_warnings, rbac_errors)
    return explain_errors_llm(question, validation_errors, safety_errors, cost_warnings, rbac_errors)
