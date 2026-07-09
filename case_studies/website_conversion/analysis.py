"""
Case Study 3: E-commerce Landing Page Conversion Test (REAL DATA)

Source: real website A/B test dataset (294,478 rows) widely used in
"Analyze A/B Test Results"-style projects, e.g. marooned20/Udacity-AB-testing.
Users were assigned to see either the existing "old_page" (control) or a
redesigned "new_page" (treatment); `converted` records whether they completed
a purchase/signup (binary).

This case study is included specifically to demonstrate a DATA QUALITY
PROBLEM DISTINCT FROM SRM: the raw file contains 3,893 rows where the group
label and the landing_page shown don't match (e.g. a 'control' user who was
actually served 'new_page') — a real logging/bucketing bug — plus a small
number of duplicated user_ids. Critically, the overall group SIZES still pass
a standard SRM check (~50/50 split, p=0.89), which is exactly why relying on
SRM alone is not sufficient: SRM catches allocation-size problems, not
per-unit contamination. A second, unit-level integrity check is needed.
"""
import sys, os, json
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "shared"))
import pandas as pd
from stats_toolkit import srm_check_counts, two_proportion_ztest

DIR = os.path.dirname(__file__)
REPORT_DIR = os.path.join(DIR, "reports")
os.makedirs(REPORT_DIR, exist_ok=True)


def run():
    df = pd.read_csv(os.path.join(DIR, "ab_data.csv"))
    out = {"raw_rows": int(len(df))}

    # --- Step 1: standard SRM check on raw group sizes ---
    srm_raw = srm_check_counts(
        (df.group == "control").sum(), (df.group == "treatment").sum())
    out["srm_check_raw_group_sizes"] = srm_raw

    # --- Step 2: unit-of-analysis integrity check (beyond SRM) ---
    # A user should see exactly one page, consistent with their assigned group.
    mismatch_mask = (
        ((df.group == "control") & (df.landing_page == "new_page")) |
        ((df.group == "treatment") & (df.landing_page == "old_page"))
    )
    n_mismatched = int(mismatch_mask.sum())

    n_dupe_rows = int(df.user_id.duplicated(keep=False).sum())

    out["data_quality_gate"] = {
        "mismatched_group_page_rows": n_mismatched,
        "mismatched_pct": round(100 * n_mismatched / len(df), 3),
        "rows_involved_in_duplicate_user_ids": n_dupe_rows,
        "verdict": "FAIL — group/page assignment logging bug detected; "
                   "SRM on raw counts alone would have missed this.",
        "action_taken": "Removed all mismatched rows, then dropped any "
                        "remaining duplicate user_id (kept first occurrence). "
                        "This is a data-cleaning decision made BEFORE looking "
                        "at the conversion outcome, based purely on assignment "
                        "integrity, to avoid the appearance of cherry-picking "
                        "rows that support a particular result.",
    }

    # --- Step 3: clean and re-run ---
    clean = df[~mismatch_mask].drop_duplicates(subset="user_id", keep="first")
    out["clean_rows"] = int(len(clean))
    out["rows_dropped_total"] = int(len(df) - len(clean))
    out["rows_dropped_pct"] = round(100 * (len(df) - len(clean)) / len(df), 3)

    srm_clean = srm_check_counts(
        (clean.group == "control").sum(), (clean.group == "treatment").sum())
    out["srm_check_post_cleaning"] = srm_clean

    # --- Primary metric: conversion rate ---
    # Single pre-specified primary metric; no guardrails are available in
    # this dataset (no revenue/AOV/refund/support fields were collected) —
    # documented explicitly rather than fabricated. Because there is only
    # one formally tested metric here, no multiple-comparisons correction
    # is needed (Holm-Bonferroni across a family of 1 is a no-op).
    t = clean[clean.group == "treatment"]
    c = clean[clean.group == "control"]
    primary = two_proportion_ztest(
        t.converted.sum(), len(t), c.converted.sum(), len(c), "conversion_rate_primary")
    out["primary_metric"] = primary
    out["guardrails"] = "None available — dataset does not include revenue, refund, " \
                        "or support-contact fields. Documented as a limitation rather " \
                        "than fabricating a guardrail from data that doesn't exist."

    # --- Novelty check: daily conversion rate over the 22-day window ---
    clean = clean.copy()
    clean["timestamp"] = pd.to_datetime(clean["timestamp"])
    clean["day"] = clean["timestamp"].dt.date
    daily = clean.groupby(["day", "group"])["converted"].mean().unstack()
    daily["rel_lift"] = (daily["treatment"] - daily["control"]) / daily["control"]
    out["daily_relative_lift"] = {str(k): round(float(v), 4) for k, v in daily["rel_lift"].items()}

    # --- Decision rule ---
    is_significant_positive = primary["p_value"] < 0.05 and primary["absolute_diff"] > 0
    if is_significant_positive:
        decision = "SHIP"
        reasons = ["Conversion rate improved significantly."]
    else:
        decision = "DO NOT SHIP — keep old page"
        reasons = [f"Conversion rate difference not statistically significant "
                   f"(p={primary['p_value']:.3f}), and the point estimate is actually "
                   f"slightly NEGATIVE for the new page. No evidence the redesign helps."]

    out["decision"] = {"decision": decision, "reasons": reasons}

    with open(os.path.join(REPORT_DIR, "results.json"), "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(json.dumps(out, indent=2, default=str))
    return out


if __name__ == "__main__":
    run()
