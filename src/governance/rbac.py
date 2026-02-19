"""
Role-Based Access Control (RBAC) for the Governed Analytics Copilot.

Roles are defined in the semantic model YAML under a top-level ``roles`` key.
Each role specifies which metrics and dimensions its members may access.

Example YAML:
  roles:
    finance:
      allowed_metrics: [revenue, aov, orders]
      allowed_dimensions: [date, country, category]
    marketing:
      allowed_metrics: [active_users, conversion_proxy]
      allowed_dimensions: [date, country, device]
    analyst:
      allowed_metrics: "*"       # wildcard — all metrics
      allowed_dimensions: "*"

If no ``roles`` section exists the system operates in *open mode* (all users
have full access).  Setting ``role=None`` also bypasses RBAC.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.core.logging import get_logger

logger = get_logger(__name__)


# ── Data classes ────────────────────────────────────────


@dataclass(frozen=True)
class Role:
    """A single RBAC role definition."""
    name: str
    allowed_metrics: list[str] = field(default_factory=list)
    allowed_dimensions: list[str] = field(default_factory=list)
    wildcard_metrics: bool = False
    wildcard_dimensions: bool = False


# ── Parsing ─────────────────────────────────────────────


def parse_roles(raw: dict[str, Any] | None) -> dict[str, Role]:
    """Parse the ``roles`` section of the semantic model YAML."""
    if not raw:
        return {}

    roles: dict[str, Role] = {}
    for name, cfg in raw.items():
        am = cfg.get("allowed_metrics", [])
        ad = cfg.get("allowed_dimensions", [])
        wm = am == "*"
        wd = ad == "*"
        roles[name] = Role(
            name=name,
            allowed_metrics=[] if wm else list(am),
            allowed_dimensions=[] if wd else list(ad),
            wildcard_metrics=wm,
            wildcard_dimensions=wd,
        )
    return roles


# ── Enforcement ─────────────────────────────────────────


def check_rbac(
    role_name: str | None,
    metric: str,
    dimensions: list[str],
    roles: dict[str, Role],
) -> list[str]:
    """Return a list of RBAC violation messages (empty = OK).

    Parameters
    ----------
    role_name:
        The user's role (``None`` or ``""`` bypasses RBAC).
    metric:
        The requested metric name.
    dimensions:
        The requested dimension names.
    roles:
        Parsed role definitions from the semantic model.

    Returns
    -------
    list[str]
        Human-readable error messages for every violation.
    """
    if not role_name:
        return []  # RBAC not enforced when role is unset

    if not roles:
        return []  # no roles defined → open mode

    role = roles.get(role_name)
    if role is None:
        return [f"Unknown role '{role_name}'. Available roles: {', '.join(sorted(roles))}"]

    errors: list[str] = []

    # Metric check
    if not role.wildcard_metrics and metric not in role.allowed_metrics:
        errors.append(
            f"Role '{role_name}' does not have access to metric '{metric}'. "
            f"Allowed metrics: {', '.join(role.allowed_metrics)}"
        )

    # Dimension check
    if not role.wildcard_dimensions:
        for dim in dimensions:
            if dim not in role.allowed_dimensions:
                errors.append(
                    f"Role '{role_name}' does not have access to dimension '{dim}'. "
                    f"Allowed dimensions: {', '.join(role.allowed_dimensions)}"
                )

    if errors:
        logger.warning("RBAC violations for role=%s: %s", role_name, errors)

    return errors
