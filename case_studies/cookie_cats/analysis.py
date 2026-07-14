"""
Case Study 1: Cookie Cats — Mobile Game Gate Placement A/B Test (REAL DATA)

90,189 players randomized to gate_30 (control) vs gate_40 (treatment).
Uses the shared abtest_guardrails package (SRM, Holm, mechanical ship rule).
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
    welch_ttest,
)
from abtest_guardrails.metrics import validate_metric_family  # noqa: E402

DATA_PATH = os.path.join(os.path.dirname(__file__), "cookie_cats.csv")
REPORT_DIR = os.path.join(os.path.dirname(__file__), "reports")
CONFIG_PATH = os.path.join(ROOT, "configs", "cookie_cats.json")
os.makedirs(REPORT_DIR, exist_ok=True)


def run():
    spec = load_preregistration(CONFIG_PATH)
    df = pd.read_csv(DATA_PATH)

    control = df[df.version == "gate_30"]
    treatment = df[df.version == "gate_40"]
    out: dict = {"n_users": int(len(df)), "preregistration": spec["experiment"]}

    outlier_mask = df.sum_gamerounds > 45000
    out["data_quality_note"] = {
        "outlier_rows_removed_for_engagement_metric": int(outlier_mask.sum()),
        "reason": (
            "sum_gamerounds=49,854 for a single user is >5,700x the median "
            "and consistent with a known bot/logging artifact; excluded "
            "only from the engagement (game rounds) guardrail calculation."
        ),
    }

    srm = srm_check_counts(
        len(control),
        len(treatment),
        expected_ratio=spec["expected_split"],
        threshold=spec["srm_threshold"],
    )
    out["srm_check"] = srm

    primary = two_proportion_ztest(
        int(treatment.retention_7.sum()),
        len(treatment),
        int(control.retention_7.sum()),
        len(control),
        spec["primary_metric"]["name"],
    )
    guardrail_ret1 = two_proportion_ztest(
        int(treatment.retention_1.sum()),
        len(treatment),
        int(control.retention_1.sum()),
        len(control),
        "retention_1_guardrail",
    )
    df_clean = df[~outlier_mask]
    eng_t = df_clean[df_clean.version == "gate_40"]["sum_gamerounds"]
    eng_c = df_clean[df_clean.version == "gate_30"]["sum_gamerounds"]
    guardrail_engagement = welch_ttest(eng_t, eng_c, "game_rounds_guardrail")

    family = [primary, guardrail_ret1, guardrail_engagement]
    validate_metric_family(spec, [m["metric"] for m in family])
    holm_bonferroni(family, alpha=spec["alpha"])
    primary, guardrail_ret1, guardrail_engagement = family

    decision = decide_ship(
        srm_detected=bool(srm["srm_detected"]),
        primary=primary,
        guardrails=[guardrail_ret1, guardrail_engagement],
        primary_desired_direction=spec["primary_metric"]["desired_direction"],
        no_ship_label="DO NOT SHIP — REVERT TO GATE AT LEVEL 30",
    )
    # Preserve richer reason text for significant wrong-way primary
    if (
        primary["significant_after_correction"]
        and primary["absolute_diff"] <= 0
        and not decision["srm_blocked"]
    ):
        decision["reasons"] = [
            "Primary metric (7-day retention) moved in the WRONG direction "
            "(treatment lower than control) and is statistically significant "
            "— this is a significant regression, not just a null result."
        ]

    out.update(
        {
            "primary_metric": primary,
            "guardrails": {
                "retention_1": guardrail_ret1,
                "game_rounds_engagement": guardrail_engagement,
            },
            "decision": decision,
        }
    )

    with open(os.path.join(REPORT_DIR, "results.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, default=str)
    print(json.dumps(out, indent=2, default=str))
    return out


if __name__ == "__main__":
    run()
