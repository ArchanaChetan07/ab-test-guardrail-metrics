"""Sample-ratio mismatch (SRM) gate via chi-square goodness-of-fit."""

from __future__ import annotations

from typing import Any

from scipy import stats


DEFAULT_SRM_THRESHOLD = 0.001


def srm_check_counts(
    n_control: int,
    n_treatment: int,
    expected_ratio: float = 0.5,
    threshold: float = DEFAULT_SRM_THRESHOLD,
) -> dict[str, Any]:
    """Chi-square goodness-of-fit SRM check from raw group sizes.

    H0: observed (control, treatment) counts match the expected split
    (default 50/50). ``threshold`` defaults to 0.001 (not 0.05): a false
    SRM alarm only costs a re-check, but a missed SRM invalidates every
    downstream metric.
    """
    n_control = int(n_control)
    n_treatment = int(n_treatment)
    n_total = n_control + n_treatment
    if n_total <= 0:
        raise ValueError("n_control + n_treatment must be > 0")
    expected_treat = n_total * expected_ratio
    expected_control = n_total * (1 - expected_ratio)
    chi2, p_value = stats.chisquare(
        [n_control, n_treatment],
        f_exp=[expected_control, expected_treat],
    )
    p_value = float(p_value)
    return {
        "n_control": n_control,
        "n_treatment": n_treatment,
        "n_total": n_total,
        "observed_ratio_treatment": round(n_treatment / n_total, 5),
        "expected_ratio_treatment": expected_ratio,
        "chi2_statistic": round(float(chi2), 4),
        "p_value": p_value,
        "srm_detected": bool(p_value < threshold),
        "threshold": threshold,
    }
