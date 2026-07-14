"""Mechanical ship / no-ship decision rules with hard SRM gate."""

from __future__ import annotations

from typing import Any, Literal


Direction = Literal["positive", "negative"]


def decide_ship(
    *,
    srm_detected: bool,
    primary: dict[str, Any],
    guardrails: list[dict[str, Any]] | None = None,
    primary_desired_direction: Direction = "positive",
    ship_label: str = "SHIP",
    no_ship_label: str = "DO NOT SHIP",
) -> dict[str, Any]:
    """Mechanical launch decision.

    Hard rule: if ``srm_detected`` is True, always return a no-ship decision
    regardless of metric significance. This is the core guardrail invariant.
    """
    guardrails = guardrails or []
    reasons: list[str] = []

    if srm_detected:
        return {
            "decision": no_ship_label,
            "reasons": [
                "SRM detected — traffic allocation is invalid; ship blocked by guardrail "
                "regardless of metric significance."
            ],
            "srm_blocked": True,
            "ship": False,
        }

    desired_positive = primary_desired_direction == "positive"
    primary_sig = bool(primary.get("significant_after_correction", primary.get("p_value", 1) < 0.05))
    abs_diff = float(primary.get("absolute_diff", 0.0))
    primary_in_desired_direction = abs_diff > 0 if desired_positive else abs_diff < 0

    ship = primary_sig and primary_in_desired_direction
    if not primary_sig:
        reasons.append(
            f"Primary metric ({primary.get('metric', 'primary')}) not significant after correction."
        )
    elif not primary_in_desired_direction:
        reasons.append(
            f"Primary metric ({primary.get('metric', 'primary')}) moved opposite the "
            f"pre-registered desired direction ({primary_desired_direction})."
        )

    guardrail_violation = False
    for g in guardrails:
        g_sig = bool(g.get("significant_after_correction", False))
        g_diff = float(g.get("absolute_diff", 0.0))
        # Guardrails: block ship on significant regressions (negative absolute_diff)
        if g_sig and g_diff < 0:
            guardrail_violation = True
            reasons.append(
                f"Guardrail violated: {g.get('metric', 'guardrail')} significantly lower in treatment."
            )

    if ship and not guardrail_violation:
        reasons.append("Primary metric moved as intended with no guardrail violations.")
        return {
            "decision": ship_label,
            "reasons": reasons,
            "srm_blocked": False,
            "ship": True,
        }

    return {
        "decision": no_ship_label,
        "reasons": reasons or ["Ship conditions not met."],
        "srm_blocked": False,
        "ship": False,
    }
