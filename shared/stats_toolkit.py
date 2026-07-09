"""
shared/stats_toolkit.py
------------------------
Common statistical building blocks reused across all three case studies, so
that every experiment in this portfolio is evaluated with the same rigor and
the same methodology, rather than each case study inventing its own ad hoc
approach.

Functions:
  - srm_check_counts        : SRM test from raw group counts (chi-square GoF)
  - two_proportion_ztest     : primary/guardrail tests on rate metrics
  - welch_ttest              : guardrail tests on continuous metrics (AOV, etc.)
  - holm_bonferroni          : multiple comparisons correction across a metric family
  - required_sample_size     : a priori power analysis for a proportion metric
  - achieved_power           : post hoc power check (used only descriptively,
                                never as a substitute for a priori design)
"""
import numpy as np
from scipy import stats
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize, proportions_ztest
from statsmodels.stats.multitest import multipletests


def srm_check_counts(n_control, n_treatment, expected_ratio=0.5, threshold=0.001):
    """Chi-square goodness-of-fit SRM check from raw group sizes.

    threshold=0.001 (not 0.05) is the standard convention: a false SRM alarm
    just costs a re-check, but a missed SRM invalidates every downstream metric.
    """
    n_total = n_control + n_treatment
    expected_treat = n_total * expected_ratio
    expected_control = n_total * (1 - expected_ratio)
    chi2, p_value = stats.chisquare([n_control, n_treatment],
                                     f_exp=[expected_control, expected_treat])
    return {
        "n_control": int(n_control),
        "n_treatment": int(n_treatment),
        "observed_ratio_treatment": round(n_treatment / n_total, 5),
        "expected_ratio_treatment": expected_ratio,
        "chi2_statistic": round(chi2, 4),
        "p_value": p_value,
        "srm_detected": p_value < threshold,
        "threshold": threshold,
    }


def two_proportion_ztest(successes_a, n_a, successes_b, n_b, label="metric"):
    """Two-proportion z-test. 'a' = treatment, 'b' = control by convention."""
    rate_a, rate_b = successes_a / n_a, successes_b / n_b
    counts = np.array([successes_a, successes_b])
    nobs = np.array([n_a, n_b])
    z_stat, p_value = proportions_ztest(counts, nobs, alternative="two-sided")
    se = np.sqrt(rate_a * (1 - rate_a) / n_a + rate_b * (1 - rate_b) / n_b)
    diff = rate_a - rate_b
    return {
        "metric": label,
        "rate_treatment": round(rate_a, 5),
        "rate_control": round(rate_b, 5),
        "absolute_diff": round(diff, 5),
        "relative_diff_pct": round(100 * diff / rate_b, 3) if rate_b != 0 else None,
        "ci_95_absolute": [round(diff - 1.96 * se, 5), round(diff + 1.96 * se, 5)],
        "z_stat": round(z_stat, 4),
        "p_value": p_value,
    }


def welch_ttest(sample_treatment, sample_control, label="metric"):
    """Welch's t-test for a continuous guardrail metric (unequal variances assumed)."""
    t_stat, p_value = stats.ttest_ind(sample_treatment, sample_control, equal_var=False)
    diff = np.mean(sample_treatment) - np.mean(sample_control)
    return {
        "metric": label,
        "mean_treatment": round(float(np.mean(sample_treatment)), 4),
        "mean_control": round(float(np.mean(sample_control)), 4),
        "absolute_diff": round(float(diff), 4),
        "relative_diff_pct": round(100 * diff / np.mean(sample_control), 3),
        "t_stat": round(t_stat, 4),
        "p_value": p_value,
    }


def holm_bonferroni(results, alpha=0.05):
    """Applies Holm-Bonferroni correction across a family of test result dicts,
    each of which must have a 'p_value' key. Adds 'p_value_holm_adjusted' and
    'significant_after_correction' to each dict in place (and returns them)."""
    pvals = [r["p_value"] for r in results]
    reject, p_adj, _, _ = multipletests(pvals, alpha=alpha, method="holm")
    for r, rej, padj in zip(results, reject, p_adj):
        r["p_value_holm_adjusted"] = round(float(padj), 6)
        r["significant_after_correction"] = bool(rej)
    return results


def required_sample_size(baseline_rate, mde_relative, alpha=0.05, power=0.8):
    """A priori sample size (per arm) for a two-proportion test."""
    target_rate = baseline_rate * (1 + mde_relative)
    effect_size = proportion_effectsize(target_rate, baseline_rate)
    analysis = NormalIndPower()
    n_per_arm = analysis.solve_power(effect_size=effect_size, alpha=alpha,
                                      power=power, ratio=1, alternative="two-sided")
    return {
        "baseline_rate": baseline_rate,
        "mde_relative": mde_relative,
        "target_rate": round(target_rate, 5),
        "alpha": alpha,
        "power": power,
        "required_n_per_arm": int(np.ceil(n_per_arm)),
    }


def achieved_power(baseline_rate, mde_relative, n_per_arm, alpha=0.05):
    """Retrospective power check: given the sample actually collected, what
    power did we really have to detect the pre-specified MDE? Used only to be
    transparent about underpowered results, never to justify moving goalposts
    after seeing the data."""
    target_rate = baseline_rate * (1 + mde_relative)
    effect_size = proportion_effectsize(target_rate, baseline_rate)
    analysis = NormalIndPower()
    power = analysis.power(effect_size=effect_size, nobs1=n_per_arm, ratio=1,
                            alpha=alpha, alternative="two-sided")
    return round(float(power), 4)
