"""
analysis.py
-----------
End-to-end analysis of the checkout-flow redesign experiment.

Pipeline:
  1. Load session-level data
  2. Sample Ratio Mismatch (SRM) check (chi-square goodness of fit vs 50/50)
  3. Primary metric test: checkout conversion rate (two-proportion z-test)
  4. Guardrail tests: AOV (Welch's t-test), 14d refund rate (z-test),
     7d support contact rate (z-test)
  5. Multiple comparisons correction (Holm-Bonferroni) across the family of
     4 formally tested metrics (1 primary + 3 guardrails)
  6. Novelty effect check: day-by-day treatment effect trend, first 10 days
     vs remaining days
  7. Ship / no-ship decision logic applied mechanically from pre-registered
     rules (see design_doc.md) -- not from post-hoc judgment calls.

Run: python3 analysis.py [--srm-demo]
"""
import argparse
import json
import os
import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.proportion import proportions_ztest
from statsmodels.stats.multitest import multipletests

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
REPORT_DIR = os.path.join(os.path.dirname(__file__), "..", "reports")
os.makedirs(REPORT_DIR, exist_ok=True)

ALPHA_FAMILYWISE = 0.05


def load_data(srm_demo=False):
    fname = "sessions_srm_demo.csv" if srm_demo else "sessions.csv"
    return pd.read_csv(os.path.join(DATA_DIR, fname))


def srm_check(df):
    counts = df["arm"].value_counts()
    n_control, n_treat = counts["control"], counts["treatment"]
    n_total = n_control + n_treat
    expected = n_total / 2
    chi2, p_value = stats.chisquare([n_control, n_treat], f_exp=[expected, expected])
    passed = p_value >= 0.001  # standard SRM threshold (stricter than 0.05
                                # because false alarms are cheap to re-check,
                                # but a real mismatch invalidates everything downstream)
    return {
        "n_control": int(n_control),
        "n_treatment": int(n_treat),
        "ratio_treatment": round(n_treat / n_total, 4),
        "chi2_statistic": round(chi2, 4),
        "p_value": p_value,
        "srm_detected": not passed,
        "threshold": 0.001,
    }


def test_primary_metric(df):
    """Two-proportion z-test on checkout conversion rate."""
    grp = df.groupby("arm")["purchased"].agg(["sum", "count"])
    conv_control = grp.loc["control", "sum"] / grp.loc["control", "count"]
    conv_treat = grp.loc["treatment", "sum"] / grp.loc["treatment", "count"]
    counts = np.array([grp.loc["treatment", "sum"], grp.loc["control", "sum"]])
    nobs = np.array([grp.loc["treatment", "count"], grp.loc["control", "count"]])
    z_stat, p_value = proportions_ztest(counts, nobs, alternative="two-sided")

    se = np.sqrt(conv_control * (1 - conv_control) / grp.loc["control", "count"]
                 + conv_treat * (1 - conv_treat) / grp.loc["treatment", "count"])
    diff = conv_treat - conv_control
    ci_low, ci_high = diff - 1.96 * se, diff + 1.96 * se

    return {
        "metric": "checkout_conversion_rate",
        "control_rate": round(conv_control, 5),
        "treatment_rate": round(conv_treat, 5),
        "absolute_diff": round(diff, 5),
        "relative_diff_pct": round(100 * diff / conv_control, 3),
        "ci_95_absolute": [round(ci_low, 5), round(ci_high, 5)],
        "z_stat": round(z_stat, 4),
        "p_value": p_value,
    }


def test_guardrail_aov(df):
    """Welch's t-test on average order value (conditional on purchase)."""
    sub = df.dropna(subset=["order_value"])
    c = sub.loc[sub.arm == "control", "order_value"]
    t = sub.loc[sub.arm == "treatment", "order_value"]
    t_stat, p_value = stats.ttest_ind(t, c, equal_var=False)
    diff = t.mean() - c.mean()
    return {
        "metric": "average_order_value",
        "control_mean": round(c.mean(), 2),
        "treatment_mean": round(t.mean(), 2),
        "absolute_diff": round(diff, 2),
        "relative_diff_pct": round(100 * diff / c.mean(), 3),
        "t_stat": round(t_stat, 4),
        "p_value": p_value,
        "guardrail_rule": "flag if treatment mean drops more than 2% relative",
    }


def test_guardrail_rate(df, col, label):
    """Two-proportion z-test for a rate-based guardrail (refund, support contact)."""
    grp = df.groupby("arm")[col].agg(["sum", "count"])
    r_c = grp.loc["control", "sum"] / grp.loc["control", "count"]
    r_t = grp.loc["treatment", "sum"] / grp.loc["treatment", "count"]
    counts = np.array([grp.loc["treatment", "sum"], grp.loc["control", "sum"]])
    nobs = np.array([grp.loc["treatment", "count"], grp.loc["control", "count"]])
    z_stat, p_value = proportions_ztest(counts, nobs, alternative="two-sided")
    diff = r_t - r_c
    return {
        "metric": label,
        "control_rate": round(r_c, 5),
        "treatment_rate": round(r_t, 5),
        "absolute_diff_pp": round(100 * diff, 3),
        "z_stat": round(z_stat, 4),
        "p_value": p_value,
    }


def novelty_check(df):
    """Compare treatment effect in days 1-10 vs days 11-28."""
    early = df[df.day <= 10]
    late = df[df.day > 10]

    def conv(sub, arm):
        s = sub[sub.arm == arm]
        return s.purchased.sum() / len(s)

    early_lift = (conv(early, "treatment") - conv(early, "control")) / conv(early, "control")
    late_lift = (conv(late, "treatment") - conv(late, "control")) / conv(late, "control")

    # Daily lift series for inspection / plotting
    daily = (df.groupby(["day", "arm"])["purchased"].mean().unstack())
    daily["relative_lift"] = (daily["treatment"] - daily["control"]) / daily["control"]
    daily["relative_lift_3d_avg"] = daily["relative_lift"].rolling(3, center=True, min_periods=1).mean()

    return {
        "early_window_days": "1-10",
        "late_window_days": "11-28",
        "early_relative_lift_pct": round(100 * early_lift, 2),
        "late_relative_lift_pct": round(100 * late_lift, 2),
        "novelty_gap_pp": round(100 * (early_lift - late_lift), 2),
        "daily_lift_series": daily["relative_lift"].round(4).to_dict(),
        "daily_lift_series_3d_smoothed": daily["relative_lift_3d_avg"].round(4).to_dict(),
    }


def apply_correction(results):
    """Holm-Bonferroni across the family of formally tested metrics."""
    labels = [r["metric"] for r in results]
    pvals = [r["p_value"] for r in results]
    reject, p_adj, _, _ = multipletests(pvals, alpha=ALPHA_FAMILYWISE, method="holm")
    for r, rej, padj in zip(results, reject, p_adj):
        r["p_value_holm_adjusted"] = round(padj, 6)
        r["significant_after_correction"] = bool(rej)
    return results


def decide_ship(primary, guardrails):
    """
    Mechanical decision rule, fixed BEFORE analysis (see design_doc.md section 5):
      - Ship if primary metric is significant after correction AND positive
      - AND no guardrail shows a statistically significant degradation
        after correction
      - Otherwise: hold / no-ship, with reason
    """
    reasons = []
    ship = True

    if not (primary["significant_after_correction"] and primary["absolute_diff"] > 0):
        ship = False
        reasons.append("Primary metric not a significant positive result after correction.")

    for g in guardrails:
        degrades = False
        if g["metric"] == "average_order_value":
            degrades = g["significant_after_correction"] and g["absolute_diff"] < 0
        else:
            # rate guardrails: degradation = treatment rate increased (refunds/support = bad)
            degrades = g["significant_after_correction"] and g.get("absolute_diff_pp", 0) > 0
        if degrades:
            ship = False
            reasons.append(f"Guardrail violated: {g['metric']} shows a significant "
                            f"degradation in the treatment arm after correction.")

    if ship:
        reasons.append("Primary metric improved significantly with no guardrail violations.")

    return {"decision": "SHIP" if ship else "HOLD / DO NOT SHIP AS-IS", "reasons": reasons}


def run(srm_demo=False):
    df = load_data(srm_demo=srm_demo)

    srm = srm_check(df)

    out = {"srm_check": srm}

    if srm["srm_detected"]:
        out["halt_reason"] = (
            "Sample Ratio Mismatch detected (p={:.2e} < {:.3f}). Per pre-registered "
            "protocol, downstream metric analysis is INVALID and must not be used for a "
            "ship decision until the assignment/logging pipeline is debugged and the "
            "test is rerun.".format(srm["p_value"], srm["threshold"])
        )
        print(json.dumps(out, indent=2, default=str))
        with open(os.path.join(REPORT_DIR, "analysis_results.json"), "w") as f:
            json.dump(out, f, indent=2, default=str)
        return out

    primary = test_primary_metric(df)
    guardrail_aov = test_guardrail_aov(df)
    guardrail_refund = test_guardrail_rate(df, "refunded", "refund_rate_14d")
    guardrail_support = test_guardrail_rate(df, "support_contact", "support_contact_rate_7d")

    family = [primary, guardrail_aov, guardrail_refund, guardrail_support]
    family = apply_correction(family)
    primary, guardrail_aov, guardrail_refund, guardrail_support = family

    novelty = novelty_check(df)

    decision = decide_ship(primary, [guardrail_aov, guardrail_refund, guardrail_support])

    out.update({
        "primary_metric": primary,
        "guardrails": {
            "average_order_value": guardrail_aov,
            "refund_rate_14d": guardrail_refund,
            "support_contact_rate_7d": guardrail_support,
        },
        "novelty_check": novelty,
        "decision": decision,
    })

    with open(os.path.join(REPORT_DIR, "analysis_results.json"), "w") as f:
        json.dump(out, f, indent=2, default=str)

    print(json.dumps(out, indent=2, default=str))
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--srm-demo", action="store_true",
                         help="Run on the deliberately corrupted SRM demo dataset")
    args = parser.parse_args()
    run(srm_demo=args.srm_demo)
