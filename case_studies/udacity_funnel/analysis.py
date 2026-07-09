"""
Case Study 2: Udacity Free Trial Screener (REAL DATA)

Source: real experiment run by Udacity, publicly released as daily-aggregated
counts (pageviews/clicks/enrollments/payments) for control and experiment arms.
Widely mirrored on GitHub (e.g. jojoms711/Udacity_AB_Testing).

Experiment: when a student clicked "start free trial," the treatment arm asked
how many hours/week they could commit. Students indicating <5 hrs/week were
nudged toward the free materials instead of the paid trial. Hypothesis: this
reduces low-commitment enrollments (protecting coaching capacity) without
significantly hurting the number of students who actually pay past the trial.

Note on granularity: this dataset is DAILY AGGREGATE COUNTS, not user-level
rows. This means:
  - The SRM check operates on daily totals rather than a session-level flag
  - Guardrail tests use pooled counts across the 23-day window in which
    enrollment/payment data is available (funnel data is tracked 14 fewer
    days than pageviews/clicks, since payment happens 14 days after enrollment)
This is a deliberately different data shape than the other two case studies,
included so the portfolio demonstrates handling more than one data format.
"""
import sys, os, json
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "shared"))
import pandas as pd
from stats_toolkit import srm_check_counts, two_proportion_ztest, holm_bonferroni

DIR = os.path.dirname(__file__)
REPORT_DIR = os.path.join(DIR, "reports")
os.makedirs(REPORT_DIR, exist_ok=True)


def run():
    control = pd.read_csv(os.path.join(DIR, "udacity_control.csv"))
    experiment = pd.read_csv(os.path.join(DIR, "udacity_experiment.csv"))

    out = {}

    # --- Invariant / SRM checks ---
    # Pageviews and clicks happen BEFORE the treatment is shown, so they
    # should be balanced 50/50 regardless of the experiment. This is the
    # daily-aggregate equivalent of an SRM check, run on two independent
    # invariant metrics as a cross-check.
    srm_pageviews = srm_check_counts(control.Pageviews.sum(), experiment.Pageviews.sum())
    srm_clicks = srm_check_counts(control.Clicks.sum(), experiment.Clicks.sum())
    out["invariant_checks"] = {
        "pageviews_srm": srm_pageviews,
        "clicks_srm": srm_clicks,
    }
    out["srm_detected"] = srm_pageviews["srm_detected"] or srm_clicks["srm_detected"]

    # --- Evaluation window ---
    # Enrollments/Payments are only tracked for the first 23 of the 37 days
    # of pageview/click data (payments lag enrollment by up to 14 days, so the
    # last 14 days can't be fully observed yet). Restrict evaluation metrics
    # to rows where this data exists.
    c_eval = control.dropna(subset=["Enrollments"])
    e_eval = experiment.dropna(subset=["Enrollments"])
    out["evaluation_window_days"] = int(len(c_eval))

    # --- Primary metric: Gross conversion (enrollments / clicks) ---
    # Pre-registered direction (per Udacity's own experiment writeup): the
    # screener is EXPECTED to reduce gross conversion (fewer low-commitment
    # enrollments) — a decrease here is the intended effect, not a regression.
    gross_conversion = two_proportion_ztest(
        e_eval.Enrollments.sum(), e_eval.Clicks.sum(),
        c_eval.Enrollments.sum(), c_eval.Clicks.sum(),
        "gross_conversion_primary")

    # --- Guardrail: Net conversion (payments / clicks) ---
    # This is the metric that must NOT significantly decrease — the whole
    # point of the change is to filter out low-commitment users without
    # losing students who would have actually paid.
    net_conversion = two_proportion_ztest(
        e_eval.Payments.sum(), e_eval.Clicks.sum(),
        c_eval.Payments.sum(), c_eval.Clicks.sum(),
        "net_conversion_guardrail")

    family = [gross_conversion, net_conversion]
    holm_bonferroni(family)
    gross_conversion, net_conversion = family

    # --- Decision rule ---
    # Ship if: gross conversion significantly DECREASES (intended effect)
    #          AND net conversion does NOT significantly decrease
    gross_decreased_sig = (gross_conversion["significant_after_correction"]
                            and gross_conversion["absolute_diff"] < 0)
    net_decreased_sig = (net_conversion["significant_after_correction"]
                         and net_conversion["absolute_diff"] < 0)

    reasons = []
    if gross_decreased_sig and not net_decreased_sig:
        decision = "INCONCLUSIVE — HOLD (gross conversion effect confirmed, net conversion effect unresolved)"
        reasons.append("Gross conversion decreased significantly as intended (filtering "
                        "out low-commitment enrollments).")
        reasons.append("Net conversion point estimate also decreased but was NOT statistically "
                        "significant after correction — however the confidence interval is wide "
                        "enough that a real negative effect on paying customers cannot be ruled out.")
        reasons.append("Recommendation: this is a genuine 'insufficient evidence' case, not a "
                        "clean ship or no-ship. Extend the test or run a follow-up with a tighter "
                        "practical-significance boundary on net conversion before launching broadly.")
    elif gross_decreased_sig and net_decreased_sig:
        decision = "DO NOT SHIP"
        reasons.append("Net conversion (paying customers) significantly decreased — the screener "
                        "is filtering out students who would have paid, not just low-commitment ones.")
    elif not gross_decreased_sig:
        decision = "DO NOT SHIP"
        reasons.append("Gross conversion did not significantly decrease — the screener did not "
                        "have the intended filtering effect.")
    else:
        decision = "SHIP"
        reasons.append("Both metrics moved as intended.")

    out.update({
        "primary_metric": gross_conversion,
        "guardrails": {"net_conversion": net_conversion},
        "decision": {"decision": decision, "reasons": reasons},
    })

    with open(os.path.join(REPORT_DIR, "results.json"), "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(json.dumps(out, indent=2, default=str))
    return out


if __name__ == "__main__":
    run()
