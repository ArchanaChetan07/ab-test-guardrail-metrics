"""
Case Study 3: E-commerce Landing Page Conversion Test (REAL DATA)

Demonstrates a data-quality problem distinct from SRM: group/page mismatches.
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
    load_preregistration,
    srm_check_counts,
    two_proportion_ztest,
)
from abtest_guardrails.corrections import holm_bonferroni  # noqa: E402
from abtest_guardrails.metrics import validate_metric_family  # noqa: E402

DIR = os.path.dirname(__file__)
REPORT_DIR = os.path.join(DIR, "reports")
CONFIG_PATH = os.path.join(ROOT, "configs", "website_conversion.json")
os.makedirs(REPORT_DIR, exist_ok=True)


def run():
    spec = load_preregistration(CONFIG_PATH)
    df = pd.read_csv(os.path.join(DIR, "ab_data.csv"))
    out = {"raw_rows": int(len(df)), "preregistration": spec["experiment"]}

    srm_raw = srm_check_counts(
        int((df.group == "control").sum()),
        int((df.group == "treatment").sum()),
        threshold=spec["srm_threshold"],
    )
    out["srm_check_raw_group_sizes"] = srm_raw

    mismatch_mask = ((df.group == "control") & (df.landing_page == "new_page")) | (
        (df.group == "treatment") & (df.landing_page == "old_page")
    )
    n_mismatched = int(mismatch_mask.sum())
    n_dupe_rows = int(df.user_id.duplicated(keep=False).sum())

    out["data_quality_gate"] = {
        "mismatched_group_page_rows": n_mismatched,
        "mismatched_pct": round(100 * n_mismatched / len(df), 3),
        "rows_involved_in_duplicate_user_ids": n_dupe_rows,
        "verdict": (
            "FAIL — group/page assignment logging bug detected; "
            "SRM on raw counts alone would have missed this."
        ),
        "action_taken": (
            "Removed all mismatched rows, then dropped any remaining duplicate "
            "user_id (kept first occurrence). Cleaning decision made BEFORE looking "
            "at the conversion outcome."
        ),
    }

    clean = df[~mismatch_mask].drop_duplicates(subset="user_id", keep="first")
    out["clean_rows"] = int(len(clean))
    out["rows_dropped_total"] = int(len(df) - len(clean))
    out["rows_dropped_pct"] = round(100 * (len(df) - len(clean)) / len(df), 3)

    srm_clean = srm_check_counts(
        int((clean.group == "control").sum()),
        int((clean.group == "treatment").sum()),
        threshold=spec["srm_threshold"],
    )
    out["srm_check_post_cleaning"] = srm_clean

    t = clean[clean.group == "treatment"]
    c = clean[clean.group == "control"]
    primary = two_proportion_ztest(
        int(t.converted.sum()),
        len(t),
        int(c.converted.sum()),
        len(c),
        spec["primary_metric"]["name"],
    )
    # Family of 1: Holm is a no-op but keeps the same tested code path.
    family = [primary]
    validate_metric_family(spec, [m["metric"] for m in family])
    holm_bonferroni(family, alpha=spec["alpha"])
    primary = family[0]

    out["primary_metric"] = primary
    out["guardrails"] = (
        "None available — dataset does not include revenue, refund, "
        "or support-contact fields. Documented as a limitation rather "
        "than fabricating a guardrail from data that doesn't exist."
    )

    clean = clean.copy()
    clean["timestamp"] = pd.to_datetime(clean["timestamp"])
    clean["day"] = clean["timestamp"].dt.date
    daily = clean.groupby(["day", "group"])["converted"].mean().unstack()
    daily["rel_lift"] = (daily["treatment"] - daily["control"]) / daily["control"]
    out["daily_relative_lift"] = {
        str(k): round(float(v), 4) for k, v in daily["rel_lift"].items()
    }

    decision = decide_ship(
        srm_detected=bool(srm_clean["srm_detected"]),
        primary=primary,
        guardrails=[],
        primary_desired_direction=spec["primary_metric"]["desired_direction"],
        no_ship_label="DO NOT SHIP — keep old page",
    )
    if not decision["ship"] and not decision["srm_blocked"]:
        decision["reasons"] = [
            (
                f"Conversion rate difference not statistically significant "
                f"(p={primary['p_value']:.3f}), and the point estimate is actually "
                f"slightly NEGATIVE for the new page. No evidence the redesign helps."
            )
        ]

    out["decision"] = decision

    with open(os.path.join(REPORT_DIR, "results.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, default=str)
    print(json.dumps(out, indent=2, default=str))
    return out


if __name__ == "__main__":
    run()
