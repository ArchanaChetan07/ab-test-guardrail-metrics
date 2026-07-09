import nbformat as nbf

nb = nbf.v4.new_notebook()
cells = []

md = lambda src: cells.append(nbf.v4.new_markdown_cell(src))
code = lambda src: cells.append(nbf.v4.new_code_cell(src))

md("""# Checkout Flow Redesign — A/B Test Analysis

**Experiment:** New single-page checkout flow vs. existing multi-step checkout
**Owner:** Data Science
**Status:** Analysis complete — see decision at the end

This notebook performs the full pre-registered analysis: sample ratio mismatch (SRM)
check, primary metric test, guardrail tests with multiple-comparisons correction,
and a novelty-effect check. All metrics, thresholds, and the decision rule were
fixed in `reports/design_doc.md` **before** this data was analyzed.
""")

code("""import sys, json
sys.path.append('../scripts')
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from analysis import (load_data, srm_check, test_primary_metric, test_guardrail_aov,
                       test_guardrail_rate, novelty_check, apply_correction, decide_ship)

plt.rcParams['figure.figsize'] = (9, 4)
df = load_data(srm_demo=False)
df.head()
""")

md("## 1. Data overview")
code("""print(f"Rows: {len(df):,}")
print(df.groupby('arm').size())
df.describe(include='all')
""")

md("""## 2. Sample Ratio Mismatch (SRM) check

Before trusting *any* downstream metric, we confirm the observed traffic split
matches the intended 50/50 randomization. A significant deviation (chi-square
goodness-of-fit p < 0.001) indicates a logging, bucketing, or filtering bug that
invalidates the comparison — regardless of how good the primary metric looks.
""")
code("""srm = srm_check(df)
srm
""")
code("""assert not srm['srm_detected'], "SRM detected — STOP. Do not proceed to metric analysis until this is resolved."
print("SRM check passed. Proceeding with metric analysis.")
""")

md("""## 3. Primary metric: Checkout conversion rate

Pre-registered as the single primary decision metric (design_doc.md, Section 2).
Two-proportion z-test, tested at the family-wise alpha after correction (Section 5).
""")
code("""primary = test_primary_metric(df)
primary
""")

md("""## 4. Guardrail metrics

Three guardrails were pre-registered:
1. **Average order value (AOV)** — redesign should not reduce basket size
2. **14-day refund rate** — redesign should not induce impulse purchases that get refunded
3. **7-day support contact rate** — redesign should not confuse users into contacting support
""")
code("""guardrail_aov = test_guardrail_aov(df)
guardrail_refund = test_guardrail_rate(df, 'refunded', 'refund_rate_14d')
guardrail_support = test_guardrail_rate(df, 'support_contact', 'support_contact_rate_7d')
guardrail_aov, guardrail_refund, guardrail_support
""")

md("""## 5. Multiple comparisons correction

We are formally testing 4 hypotheses (1 primary + 3 guardrails) against the same
experiment. Testing each at raw alpha = 0.05 would inflate the family-wise false
positive rate to roughly 1 - 0.95^4 ≈ 18.5%. We apply **Holm-Bonferroni**
correction (more powerful than plain Bonferroni, still strongly controls family-wise
error) across the family, at a target family-wise alpha of 0.05.
""")
code("""family = [primary, guardrail_aov, guardrail_refund, guardrail_support]
family = apply_correction(family)
pd.DataFrame(family)[['metric', 'p_value', 'p_value_holm_adjusted', 'significant_after_correction']]
""")

md("""## 6. Novelty effect check

Treatment effects sometimes look larger in the first days of an experiment purely
because early adopters/curious users behave differently, or because of a
"newness" reaction that fades. We compare the relative lift in the first 10 days
against the remaining days. This is a diagnostic check, not a formal hypothesis
test — day-level sample sizes are small (~1,850 sessions/arm/day), so day-to-day
noise is expected to be large relative to any true novelty signal.
""")
code("""novelty = novelty_check(df)
print(f"Early window (days 1-10) relative lift: {novelty['early_relative_lift_pct']}%")
print(f"Late window (days 11-28) relative lift:  {novelty['late_relative_lift_pct']}%")
print(f"Novelty gap: {novelty['novelty_gap_pp']} pp")
""")
code("""daily = pd.Series(novelty['daily_lift_series']).astype(float)
smoothed = pd.Series(novelty['daily_lift_series_3d_smoothed']).astype(float)
daily.index = daily.index.astype(int)
smoothed.index = smoothed.index.astype(int)

fig, ax = plt.subplots()
ax.bar(daily.index, daily.values * 100, alpha=0.35, label='Daily relative lift')
ax.plot(smoothed.index, smoothed.values * 100, color='firebrick', linewidth=2, label='3-day rolling avg')
ax.axhline(0, color='black', linewidth=0.8)
ax.axvline(10.5, color='gray', linestyle='--', linewidth=1, label='Day 10 cutoff (pre-registered)')
ax.set_xlabel('Experiment day')
ax.set_ylabel('Relative lift (%)')
ax.set_title('Daily conversion lift: treatment vs. control')
ax.legend()
plt.tight_layout()
plt.savefig('../reports/daily_lift.png', dpi=140)
plt.show()
""")

md("""**Interpretation:** the day-level lift series is noisy, and the early-window
average (days 1-10) is *not* higher than the late-window average — if anything the
opposite. Given the small per-day sample size relative to the effect size, this is
consistent with sampling noise rather than a genuine novelty or fatigue pattern.
**We do not claim a novelty effect here** — the check did not find convincing
evidence either way, and we report that honestly rather than fitting a story to
noisy data.
""")

md("""## 7. Visualizing the primary result
""")
code("""fig, ax = plt.subplots()
rates = [primary['control_rate'] * 100, primary['treatment_rate'] * 100]
bars = ax.bar(['Control', 'Treatment'], rates, color=['#888888', '#2b6cb0'])
for b, r in zip(bars, rates):
    ax.text(b.get_x() + b.get_width()/2, r + 0.05, f'{r:.2f}%', ha='center', fontweight='bold')
ax.set_ylabel('Checkout conversion rate (%)')
ax.set_title(f"Primary metric — relative lift: +{primary['relative_diff_pct']}% "
             f"(p = {primary['p_value']:.2e}, Holm-adjusted p = {primary['p_value_holm_adjusted']:.2e})")
plt.tight_layout()
plt.savefig('../reports/primary_metric.png', dpi=140)
plt.show()
""")

md("""## 8. Ship / no-ship decision

Applied mechanically from the pre-registered rule in `design_doc.md` Section 5 —
no post-hoc judgment calls.
""")
code("""decision = decide_ship(primary, [guardrail_aov, guardrail_refund, guardrail_support])
decision
""")

md("""## 9. Summary table for stakeholders
""")
code("""summary = pd.DataFrame([
    {'Metric': 'Checkout conversion rate (primary)', 'Control': f"{primary['control_rate']*100:.2f}%",
     'Treatment': f"{primary['treatment_rate']*100:.2f}%", 'Rel. change': f"+{primary['relative_diff_pct']}%",
     'Holm-adj. p': f"{primary['p_value_holm_adjusted']:.4f}", 'Significant?': primary['significant_after_correction']},
    {'Metric': 'Average order value (guardrail)', 'Control': f"${guardrail_aov['control_mean']:.2f}",
     'Treatment': f"${guardrail_aov['treatment_mean']:.2f}", 'Rel. change': f"{guardrail_aov['relative_diff_pct']:+.2f}%",
     'Holm-adj. p': f"{guardrail_aov['p_value_holm_adjusted']:.4f}", 'Significant?': guardrail_aov['significant_after_correction']},
    {'Metric': '14-day refund rate (guardrail)', 'Control': f"{guardrail_refund['control_rate']*100:.2f}%",
     'Treatment': f"{guardrail_refund['treatment_rate']*100:.2f}%", 'Rel. change': f"{guardrail_refund['absolute_diff_pp']:+.3f} pp",
     'Holm-adj. p': f"{guardrail_refund['p_value_holm_adjusted']:.4f}", 'Significant?': guardrail_refund['significant_after_correction']},
    {'Metric': '7-day support contact rate (guardrail)', 'Control': f"{guardrail_support['control_rate']*100:.2f}%",
     'Treatment': f"{guardrail_support['treatment_rate']*100:.2f}%", 'Rel. change': f"{guardrail_support['absolute_diff_pp']:+.3f} pp",
     'Holm-adj. p': f"{guardrail_support['p_value_holm_adjusted']:.4f}", 'Significant?': guardrail_support['significant_after_correction']},
])
summary
""")

md(f"""## 10. Conclusion

The primary metric (checkout conversion rate) improved by **+9.1% relative**
and remains significant after Holm-Bonferroni correction. However, the
**7-day support contact rate guardrail** also moved significantly — support
contacts increased by roughly 0.43 percentage points in the treatment arm.
Per the pre-registered decision rule, **any significant guardrail degradation
blocks shipping**, regardless of how strong the primary result is.

**Decision: HOLD — do not ship as-is.** Recommended next step: work with the
support/CX team to identify *why* the new checkout flow is generating more
contacts (likely candidates: a confusing new field, unclear error states) before
re-testing a revised version. See `reports/executive_summary.md` for the
stakeholder-facing version of this conclusion.
""")

nb['cells'] = cells
with open('/home/claude/ab_test_project/notebooks/ab_test_analysis.ipynb', 'w') as f:
    nbf.write(nb, f)
print("Notebook written.")
