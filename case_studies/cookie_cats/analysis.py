"""
Case Study 1: Cookie Cats — Mobile Game Gate Placement A/B Test (REAL DATA)

Source: public dataset released alongside a well-known DataCamp project,
widely mirrored (e.g. github.com/ryanschaub/Mobile-Games-A-B-Testing-with-Cookie-Cats).
90,189 players, randomized into two arms based on whether the first
progression "gate" (a forced wait / IAP prompt) was placed at level 30
(control, gate_30 — the original design) or moved to level 40 (treatment,
gate_40 — the proposed change).

This is a REAL experiment that was actually run by Tactile Entertainment,
not a synthetic dataset. We treat the original design intent (moving the
gate later, hypothesizing this increases early engagement without hurting
retention) as the pre-registered hypothesis, and apply the same rigor
(SRM check, guardrails, correction, decision rule) as if we were the
analyst at the time.
"""
import sys, os, json
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "shared"))
import pandas as pd
from stats_toolkit import srm_check_counts, two_proportion_ztest, welch_ttest, holm_bonferroni

DATA_PATH = os.path.join(os.path.dirname(__file__), "cookie_cats.csv")
REPORT_DIR = os.path.join(os.path.dirname(__file__), "reports")
os.makedirs(REPORT_DIR, exist_ok=True)


def run():
    df = pd.read_csv(DATA_PATH)

    control = df[df.version == "gate_30"]   # original design
    treatment = df[df.version == "gate_40"]  # proposed change

    out = {}

    # --- Data quality: known outlier ---
    # One user recorded 49,854 game rounds (~5,700x the median) — far beyond
    # what's physically plausible in the test window and consistent with a
    # known bot/instrumentation artifact widely noted in analyses of this
    # dataset. Documented and excluded from the engagement guardrail only
    # (retention metrics are booleans and unaffected by this outlier).
    outlier_mask = df.sum_gamerounds > 45000
    out["data_quality_note"] = {
        "outlier_rows_removed_for_engagement_metric": int(outlier_mask.sum()),
        "reason": "sum_gamerounds=49,854 for a single user is >5,700x the median "
                  "and consistent with a known bot/logging artifact; excluded "
                  "only from the engagement (game rounds) guardrail calculation.",
    }

    # --- SRM check ---
    srm = srm_check_counts(len(control), len(treatment))
    out["srm_check"] = srm

    # --- Primary metric: 7-day retention ---
    # Chosen as primary (rather than 1-day retention) because the business
    # question is whether delaying the gate helps LONG-RUN engagement/revenue,
    # not just whether people open the app once more the next day.
    primary = two_proportion_ztest(
        treatment.retention_7.sum(), len(treatment),
        control.retention_7.sum(), len(control), "retention_7_primary")

    # --- Guardrails ---
    # 1) 1-day retention: should not collapse even if 7-day is the real target
    guardrail_ret1 = two_proportion_ztest(
        treatment.retention_1.sum(), len(treatment),
        control.retention_1.sum(), len(control), "retention_1_guardrail")

    # 2) engagement depth (game rounds played) — moving the gate later
    #    could artificially inflate rounds played without real retention benefit;
    #    check it doesn't silently drop instead.
    df_clean = df[~outlier_mask]
    eng_t = df_clean[df_clean.version == "gate_40"]["sum_gamerounds"]
    eng_c = df_clean[df_clean.version == "gate_30"]["sum_gamerounds"]
    guardrail_engagement = welch_ttest(eng_t, eng_c, "game_rounds_guardrail")

    family = [primary, guardrail_ret1, guardrail_engagement]
    holm_bonferroni(family)
    primary, guardrail_ret1, guardrail_engagement = family

    # --- Decision rule (same logic pattern as Project 1's simulated case) ---
    ship = primary["significant_after_correction"] and primary["absolute_diff"] > 0
    reasons = []
    if not ship:
        if not primary["significant_after_correction"]:
            reasons.append("Primary metric (7-day retention) not significant after correction.")
        elif primary["absolute_diff"] <= 0:
            reasons.append("Primary metric (7-day retention) moved in the WRONG direction "
                            "(treatment lower than control) and is statistically significant "
                            "— this is a significant regression, not just a null result.")
    guardrail_violation = False
    if guardrail_ret1["significant_after_correction"] and guardrail_ret1["absolute_diff"] < 0:
        guardrail_violation = True
        reasons.append("Guardrail violated: 1-day retention also significantly lower in treatment.")
    if guardrail_engagement["significant_after_correction"] and guardrail_engagement["absolute_diff"] < 0:
        guardrail_violation = True
        reasons.append("Guardrail violated: engagement (game rounds) significantly lower in treatment.")

    decision = "DO NOT SHIP — REVERT TO GATE AT LEVEL 30" if (not ship or guardrail_violation) else "SHIP"
    if ship and not guardrail_violation:
        reasons.append("Primary metric improved significantly with no guardrail violations.")

    out.update({
        "primary_metric": primary,
        "guardrails": {
            "retention_1": guardrail_ret1,
            "game_rounds_engagement": guardrail_engagement,
        },
        "decision": {"decision": decision, "reasons": reasons},
    })

    with open(os.path.join(REPORT_DIR, "results.json"), "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(json.dumps(out, indent=2, default=str))
    return out


if __name__ == "__main__":
    run()
