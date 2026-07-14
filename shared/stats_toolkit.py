"""Backward-compatible re-exports; prefer `import abtest_guardrails`."""

from abtest_guardrails.srm import srm_check_counts
from abtest_guardrails.metrics import two_proportion_ztest, welch_ttest
from abtest_guardrails.corrections import holm_bonferroni
from abtest_guardrails.decision import decide_ship

# Optional power helpers retained for the synthetic checkout notebook / design doc.
import numpy as np
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize


def required_sample_size(baseline_rate, mde_relative, alpha=0.05, power=0.8):
    target_rate = baseline_rate * (1 + mde_relative)
    effect_size = proportion_effectsize(target_rate, baseline_rate)
    analysis = NormalIndPower()
    n_per_arm = analysis.solve_power(
        effect_size=effect_size, alpha=alpha, power=power, ratio=1, alternative="two-sided"
    )
    return {
        "baseline_rate": baseline_rate,
        "mde_relative": mde_relative,
        "target_rate": round(target_rate, 5),
        "alpha": alpha,
        "power": power,
        "required_n_per_arm": int(np.ceil(n_per_arm)),
    }


def achieved_power(baseline_rate, mde_relative, n_per_arm, alpha=0.05):
    target_rate = baseline_rate * (1 + mde_relative)
    effect_size = proportion_effectsize(target_rate, baseline_rate)
    analysis = NormalIndPower()
    power = analysis.power(
        effect_size=effect_size, nobs1=n_per_arm, ratio=1, alpha=alpha, alternative="two-sided"
    )
    return round(float(power), 4)


__all__ = [
    "srm_check_counts",
    "two_proportion_ztest",
    "welch_ttest",
    "holm_bonferroni",
    "decide_ship",
    "required_sample_size",
    "achieved_power",
]
