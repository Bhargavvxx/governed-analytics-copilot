"""
Natural-language metric & dimension suggestions.

When a user types a partial or ambiguous term (e.g. ``"revenue"``), this
module returns ranked suggestions from the semantic model catalog using
a combination of:
  - Exact/prefix matching
  - Token overlap (Jaccard-like)
  - Levenshtein edit-distance similarity

No external dependencies — pure Python implementation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.governance.semantic_loader import load_semantic_model, SemanticModel
from src.core.logging import get_logger

logger = get_logger(__name__)


# ── Data classes ────────────────────────────────────────


@dataclass
class Suggestion:
    """A single metric or dimension suggestion."""
    name: str
    kind: str  # "metric" or "dimension"
    description: str
    score: float  # 0.0 – 1.0, higher is better match
    is_derived: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "description": self.description,
            "score": round(self.score, 3),
            "is_derived": self.is_derived,
        }


# ── Similarity helpers ──────────────────────────────────


def _levenshtein(a: str, b: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    if len(a) < len(b):
        return _levenshtein(b, a)
    if not b:
        return len(a)

    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            cost = 0 if ca == cb else 1
            curr.append(min(curr[j] + 1, prev[j + 1] + 1, prev[j] + cost))
        prev = curr
    return prev[-1]


def _normalised_edit_sim(a: str, b: str) -> float:
    """Normalised similarity based on Levenshtein distance (1.0 = identical)."""
    max_len = max(len(a), len(b))
    if max_len == 0:
        return 1.0
    return 1.0 - _levenshtein(a, b) / max_len


def _tokenize(text: str) -> set[str]:
    """Split text into lowercase alphanumeric tokens."""
    return {t for t in text.lower().replace("_", " ").split() if t}


def _jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity between two token sets."""
    if not a and not b:
        return 1.0
    intersection = a & b
    union = a | b
    return len(intersection) / len(union) if union else 0.0


def _score(query: str, name: str, description: str) -> float:
    """Compute a composite similarity score (0–1).

    Scoring breakdown:
      - 0.50 weight: edit-distance similarity on name
      - 0.25 weight: Jaccard token overlap on name
      - 0.15 weight: Jaccard token overlap on description
      - 0.10 bonus: exact prefix match
    """
    q_lower = query.lower().strip()
    n_lower = name.lower().strip()

    edit_sim = _normalised_edit_sim(q_lower, n_lower)
    name_jaccard = _jaccard(_tokenize(q_lower), _tokenize(n_lower))
    desc_jaccard = _jaccard(_tokenize(q_lower), _tokenize(description.lower()))
    prefix_bonus = 1.0 if n_lower.startswith(q_lower) or q_lower.startswith(n_lower) else 0.0

    return 0.50 * edit_sim + 0.25 * name_jaccard + 0.15 * desc_jaccard + 0.10 * prefix_bonus


# ── Public API ──────────────────────────────────────────


def suggest_metrics(
    query: str,
    model: SemanticModel | None = None,
    top_k: int = 5,
    min_score: float = 0.20,
) -> list[Suggestion]:
    """Return metric suggestions ranked by relevance.

    Parameters
    ----------
    query : str
        The user's partial / ambiguous input.
    model : SemanticModel, optional
        Pre-loaded model; loads from YAML if not given.
    top_k : int
        Maximum number of suggestions to return.
    min_score : float
        Minimum similarity score to include.

    Returns
    -------
    list[Suggestion]
        Sorted descending by score.
    """
    if model is None:
        model = load_semantic_model()

    suggestions: list[Suggestion] = []
    for m in model.metrics.values():
        s = _score(query, m.name, m.description)
        if s >= min_score:
            suggestions.append(Suggestion(
                name=m.name,
                kind="metric",
                description=m.description,
                score=s,
                is_derived=m.is_derived,
            ))

    suggestions.sort(key=lambda x: x.score, reverse=True)
    return suggestions[:top_k]


def suggest_dimensions(
    query: str,
    model: SemanticModel | None = None,
    top_k: int = 5,
    min_score: float = 0.20,
) -> list[Suggestion]:
    """Return dimension suggestions ranked by relevance."""
    if model is None:
        model = load_semantic_model()

    suggestions: list[Suggestion] = []
    for d in model.dimensions.values():
        s = _score(query, d.name, f"column {d.column} in {d.table}")
        if s >= min_score:
            suggestions.append(Suggestion(
                name=d.name,
                kind="dimension",
                description=f"Column: {d.column}",
                score=s,
            ))

    suggestions.sort(key=lambda x: x.score, reverse=True)
    return suggestions[:top_k]


def suggest(
    query: str,
    model: SemanticModel | None = None,
    top_k: int = 6,
    min_score: float = 0.20,
) -> list[Suggestion]:
    """Return combined metric + dimension suggestions, sorted by score.

    This is the primary entry point for the suggestion feature.
    """
    if model is None:
        model = load_semantic_model()

    all_suggestions = (
        suggest_metrics(query, model=model, top_k=top_k, min_score=min_score)
        + suggest_dimensions(query, model=model, top_k=top_k, min_score=min_score)
    )
    all_suggestions.sort(key=lambda x: x.score, reverse=True)
    return all_suggestions[:top_k]
