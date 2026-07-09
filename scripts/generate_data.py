"""
generate_data.py
-----------------
Simulates a 28-day randomized checkout-flow A/B test for a mid-size e-commerce
startup. The simulation encodes a KNOWN ground truth (injected effect sizes)
so the analysis pipeline can be validated end-to-end before being trusted on
real data. This mirrors how a rigorous DS team would unit-test an analysis
pipeline against synthetic data with a known answer.

Ground truth injected into the data (kept in GROUND_TRUTH.json so the
analysis notebook can be scored against it, then deleted / ignored when
treating the data as "real" for the exercise):

- True relative lift on primary metric (checkout conversion rate): +6.0%
- Guardrail 1 (Average Order Value):  0% true effect (flat)
- Guardrail 2 (14-day refund rate):   0% true effect (flat)
- Guardrail 3 (support contact rate): +0.4pp true DEGRADATION (small regression,
  deliberately injected so the pipeline demonstrates it can catch a guardrail
  violation, not just rubber-stamp ship decisions)
- Novelty effect: treatment effect is inflated by 40% relative during days 1-5,
  then decays to the true effect by day 10 (tests analyst's ability to detect
  novelty rather than mistake it for the steady-state effect)
- Sample ratio: exactly 50/50 by design, with one deliberately corrupted
  variant of the dataset (data/sessions_srm.csv) that has a 51.5/48.5 split
  caused by a simulated bot-filtering bug, to demonstrate the SRM check
  actually catching a real problem.
"""
import numpy as np
import pandas as pd
import json
import os

RNG = np.random.default_rng(42)
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(OUT_DIR, exist_ok=True)

N_DAYS = 28
SESSIONS_PER_DAY = 3700  # ~46k pageviews/day scaled down; realistic for a mid-size startup

BASELINE_CONV = 0.062          # 6.2% checkout conversion rate (sessions -> purchase)
BASELINE_AOV_MEAN = 68.50       # $ average order value, conditional on purchase
BASELINE_AOV_SD = 24.0
BASELINE_REFUND_RATE = 0.045    # 4.5% of orders refunded within 14 days
BASELINE_SUPPORT_RATE = 0.018   # 1.8% of sessions generate a support contact within 7 days

TRUE_LIFT_REL = 0.08            # +8% relative lift on conversion, steady state (matches pre-registered MDE)
GUARDRAIL_AOV_EFFECT = 0.0
GUARDRAIL_REFUND_EFFECT = 0.0
GUARDRAIL_SUPPORT_EFFECT_PP = 0.004  # +0.4 percentage points (degradation)

NOVELTY_MULTIPLIER_DAY1 = 1.40   # effect is 40% larger on day 1
NOVELTY_DECAY_DAYS = 10          # decays linearly back to steady state by day 10


def novelty_factor(day_idx):
    """Relative inflation multiplier on the treatment effect for a given day (0-indexed)."""
    if day_idx >= NOVELTY_DECAY_DAYS:
        return 1.0
    frac_remaining = 1 - day_idx / NOVELTY_DECAY_DAYS
    return 1.0 + (NOVELTY_MULTIPLIER_DAY1 - 1.0) * frac_remaining


def simulate(srm_bug=False, seed=42):
    rng = np.random.default_rng(seed)
    rows = []
    session_id = 0
    for day in range(N_DAYS):
        n_today = SESSIONS_PER_DAY + rng.integers(-150, 150)

        if srm_bug:
            # Simulated bug: a bot-filter deployed alongside the experiment
            # disproportionately drops ~3% of CONTROL sessions (logging race
            # condition), producing a sample ratio mismatch unrelated to the
            # treatment itself.
            p_treat = 0.515
        else:
            p_treat = 0.50

        assignment = rng.choice(["control", "treatment"], size=n_today,
                                 p=[1 - p_treat, p_treat])

        for arm in assignment:
            session_id += 1
            is_treat = arm == "treatment"

            eff_mult = novelty_factor(day) if is_treat else 1.0
            conv_p = BASELINE_CONV * (1 + TRUE_LIFT_REL * eff_mult) if is_treat else BASELINE_CONV
            conv_p = min(conv_p, 0.99)
            purchased = rng.random() < conv_p

            order_value = np.nan
            refunded = False
            if purchased:
                aov_mean = BASELINE_AOV_MEAN * (1 + (GUARDRAIL_AOV_EFFECT if is_treat else 0))
                order_value = max(5.0, rng.normal(aov_mean, BASELINE_AOV_SD))
                refund_p = BASELINE_REFUND_RATE + (GUARDRAIL_REFUND_EFFECT if is_treat else 0)
                refunded = rng.random() < refund_p

            support_p = BASELINE_SUPPORT_RATE + (GUARDRAIL_SUPPORT_EFFECT_PP if is_treat else 0)
            support_contact = rng.random() < support_p

            rows.append({
                "session_id": session_id,
                "day": day + 1,
                "arm": arm,
                "purchased": int(purchased),
                "order_value": round(order_value, 2) if purchased else np.nan,
                "refunded": int(refunded) if purchased else 0,
                "support_contact": int(support_contact),
            })

    return pd.DataFrame(rows)


if __name__ == "__main__":
    df_clean = simulate(srm_bug=False, seed=42)
    df_clean.to_csv(os.path.join(OUT_DIR, "sessions.csv"), index=False)

    df_srm = simulate(srm_bug=True, seed=43)
    df_srm.to_csv(os.path.join(OUT_DIR, "sessions_srm_demo.csv"), index=False)

    ground_truth = {
        "primary_metric": "checkout_conversion_rate",
        "baseline_conversion_rate": BASELINE_CONV,
        "true_relative_lift": TRUE_LIFT_REL,
        "pre_registered_mde": 0.08,
        "guardrails": {
            "average_order_value": {"true_relative_effect": GUARDRAIL_AOV_EFFECT},
            "refund_rate_14d": {"true_relative_effect": GUARDRAIL_REFUND_EFFECT},
            "support_contact_rate_7d": {"true_absolute_effect_pp": GUARDRAIL_SUPPORT_EFFECT_PP},
        },
        "novelty_effect": {
            "day1_multiplier": NOVELTY_MULTIPLIER_DAY1,
            "decays_to_steady_state_by_day": NOVELTY_DECAY_DAYS,
        },
        "note": "This file is the answer key used ONLY to validate the analysis "
                "pipeline. In the deliverables, the analysis is written as if "
                "ground truth were unknown, exactly as it would be with real data.",
    }
    with open(os.path.join(OUT_DIR, "GROUND_TRUTH.json"), "w") as f:
        json.dump(ground_truth, f, indent=2)

    print("Clean dataset:", df_clean.shape)
    print(df_clean.groupby("arm").size())
    print("\nSRM-demo dataset:", df_srm.shape)
    print(df_srm.groupby("arm").size())
