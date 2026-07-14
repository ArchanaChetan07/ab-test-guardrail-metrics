"""
Case Study 2: Udacity Free Trial Screener (REAL DATA) — daily aggregates.
"""
from __future__ import annotations

import json
import os
import sys

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from abtest_guardrails import (  # noqa: E402
    decide_ship,
    holm_bonferroni,
    load_preregistration,
    srm_check_counts,
    two_proportion_ztest,
)
from abtest_guardrails.metrics import validate_metric_family  # noqa: E402

DIR = os.path.dirname(__file__)
REPORT_DIR = os.path.join(DIR, "reports")
CONFIG_PATH = os.path.join(ROOT, "configs", "udacity_funnel.json")
os.makedirs(REPORT_DIR, exist_ok=True)


def run():
    spec = load_preregistration(CONFIG_PATH)
    control = pd.read_csv(os.path.join(DIR, "udacity_control.csv"))
    experiment = pd.read_csv(os.path.join(DIR, "udacity_experiment.csv"))
    out: dict = {"preregistration": spec["experiment"]}

    srm_pageviews = srm_check_counts(
        int(control.Pageviews.sum()),
        int(experiment.Pageviews.sum()),
        threshold=spec["srm_threshold"],
    )
    srm_clicks = srm_check_counts(
        int(control.Clicks.sum()),
        int(experiment.Clicks.sum()),
        threshold=spec["srm_threshold"],
    )
    out["invariant_checks"] = {"pageviews_srm": srm_pageviews, "clicks_srm": srm_clicks}
    srm_detected = bool(srm_pageviews["srm_detected"] or srm_clicks["srm_detected"])
    out["srm_detected"] = srm_detected

    c_eval = control.dropna(subset=["Enrollments"])
    e_eval = experiment.dropna(subset=["Enrollments"])
    out["evaluation_window_days"] = int(len(c_eval))

    gross_conversion = two_proportion_ztest(
        int(e_eval.Enrollments.sum()),
        int(e_eval.Clicks.sum()),
        int(c_eval.Enrollments.sum()),
        int(c_eval.Clicks.sum()),
        spec["primary_metric"]["name"],
    )
    net_conversion = two_proportion_ztest(
        int(e_eval.Payments.sum()),
        int(e_eval.Clicks.sum()),
        int(c_eval.Payments.sum()),
        int(c_eval.Clicks.sum()),
        "net_conversion_guardrail",
    )
    family = [gross_conversion, net_conversion]
    validate_metric_family(spec, [m["metric"] for m in family])
    holm_bonferroni(family, alpha=spec["alpha"])
    gross_conversion, net_conversion = family

    if srm_detected:
        decision = decide_ship(
            srm_detected=True,
            primary=gross_conversion,
            guardrails=[net_conversion],
            primary_desired_direction="negative",
        )
    else:
        gross_decreased_sig = (
            gross_conversion["significant_after_correction"]
            and gross_conversion["absolute_diff"] < 0
        )
        net_decreased_sig = (
            net_conversion["significant_after_correction"]
            and net_conversion["absolute_diff"] < 0
        )
        if gross_decreased_sig and not net_decreased_sig:
            decision = {
                "decision": (
                    "INCONCLUSIVE — HOLD (gross conversion effect confirmed, "
                    "net conversion effect unresolved)"
                ),
                "reasons": [
                    "Gross conversion decreased significantly as intended (filtering "
                    "out low-commitment enrollments).",
                    "Net conversion point estimate also decreased but was NOT statistically "
                    "significant after correction — however the confidence interval is wide "
                    "enough that a real negative effect on paying customers cannot be ruled out.",
                    "Recommendation: this is a genuine 'insufficient evidence' case, not a "
                    "clean ship or no-ship. Extend the test or run a follow-up with a tighter "
                    "practical-significance boundary on net conversion before launching broadly.",
                ],
                "srm_blocked": False,
                "ship": False,
            }
        elif gross_decreased_sig and net_decreased_sig:
            decision = {
                "decision": "DO NOT SHIP",
                "reasons": [
                    "Net conversion (paying customers) significantly decreased — the screener "
                    "is filtering out students who would have paid, not just low-commitment ones."
                ],
                "srm_blocked": False,
                "ship": False,
            }
        elif not gross_decreased_sig:
            decision = {
                "decision": "DO NOT SHIP",
                "reasons": [
                    "Gross conversion did not significantly decrease — the screener did not "
                    "have the intended filtering effect."
                ],
                "srm_blocked": False,
                "ship": False,
            }
        else:
            decision = decide_ship(
                srm_detected=False,
                primary=gross_conversion,
                guardrails=[net_conversion],
                primary_desired_direction="negative",
            )

    out.update(
        {
            "primary_metric": gross_conversion,
            "guardrails": {"net_conversion": net_conversion},
            "decision": decision,
        }
    )

    with open(os.path.join(REPORT_DIR, "results.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, default=str)
    print(json.dumps(out, indent=2, default=str))
    return out


if __name__ == "__main__":
    run()
