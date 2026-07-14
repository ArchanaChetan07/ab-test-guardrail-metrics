"""Pre-registered metric specs + core metric tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from statsmodels.stats.proportion import proportions_ztest
from scipy import stats


def load_preregistration(path: str | Path) -> dict[str, Any]:
    """Load a locked pre-registration JSON (metrics declared before analysis)."""
    path = Path(path)
    spec = json.loads(path.read_text(encoding="utf-8"))
    required = {"experiment", "primary_metric", "guardrail_metrics", "alpha", "srm_threshold"}
    missing = required - set(spec)
    if missing:
        raise ValueError(f"Pre-registration missing keys: {sorted(missing)}")
    if not isinstance(spec["guardrail_metrics"], list):
        raise ValueError("guardrail_metrics must be a list")
    return spec


def validate_metric_family(spec: dict[str, Any], observed_metric_names: list[str]) -> None:
    """Ensure analyzed metrics match the pre-registered family (no post-hoc adds)."""
    expected = [spec["primary_metric"]["name"]] + [
        g["name"] for g in spec["guardrail_metrics"]
    ]
    if list(observed_metric_names) != expected:
        raise ValueError(
            "Analyzed metrics do not match pre-registration.\n"
            f"expected={expected}\nobserved={list(observed_metric_names)}"
        )


def two_proportion_ztest(
    successes_a: int,
    n_a: int,
    successes_b: int,
    n_b: int,
    label: str = "metric",
) -> dict[str, Any]:
    """Two-proportion z-test. 'a' = treatment, 'b' = control by convention."""
    rate_a, rate_b = successes_a / n_a, successes_b / n_b
    counts = np.array([successes_a, successes_b])
    nobs = np.array([n_a, n_b])
    z_stat, p_value = proportions_ztest(counts, nobs, alternative="two-sided")
    se = np.sqrt(rate_a * (1 - rate_a) / n_a + rate_b * (1 - rate_b) / n_b)
    diff = rate_a - rate_b
    return {
        "metric": label,
        "rate_treatment": round(float(rate_a), 5),
        "rate_control": round(float(rate_b), 5),
        "absolute_diff": round(float(diff), 5),
        "relative_diff_pct": round(100 * diff / rate_b, 3) if rate_b != 0 else None,
        "ci_95_absolute": [round(float(diff - 1.96 * se), 5), round(float(diff + 1.96 * se), 5)],
        "z_stat": round(float(z_stat), 4),
        "p_value": float(p_value),
    }


def welch_ttest(
    sample_treatment,
    sample_control,
    label: str = "metric",
) -> dict[str, Any]:
    """Welch's t-test for a continuous guardrail metric (unequal variances)."""
    t_stat, p_value = stats.ttest_ind(sample_treatment, sample_control, equal_var=False)
    diff = float(np.mean(sample_treatment) - np.mean(sample_control))
    mean_c = float(np.mean(sample_control))
    return {
        "metric": label,
        "mean_treatment": round(float(np.mean(sample_treatment)), 4),
        "mean_control": round(mean_c, 4),
        "absolute_diff": round(diff, 4),
        "relative_diff_pct": round(100 * diff / mean_c, 3) if mean_c != 0 else None,
        "t_stat": round(float(t_stat), 4),
        "p_value": float(p_value),
    }
