# Experiment Design Document

**Experiment name:** Checkout Flow Redesign — Single-Page Checkout
**Author:** Data Science
**Status:** PRE-REGISTERED — locked before data collection began
**Date locked:** 2026-06-01

> This document is intentionally written and locked *before* any experiment
> data is analyzed. Every threshold, metric, and decision rule referenced in
> the analysis notebook and executive summary traces back to a specific
> section here. If a stakeholder asks "did you decide that after seeing the
> result?" the answer for every number in this doc is no.

---

## 1. Background & Hypothesis

The current checkout is a 3-step flow (cart → shipping/billing → review &
pay). Session-replay review and support tickets suggest users are dropping
off between steps, particularly on mobile. Product proposes collapsing this
into a single-page checkout with inline validation.

**Hypothesis:** Reducing checkout to a single page will reduce friction and
increase the share of sessions that complete a purchase, without meaningfully
harming order size, refund behavior, or the need for customer support.

**Unit of randomization:** session (cookie-based), assigned at the moment a
user reaches the checkout entry point. 50/50 control vs. treatment.

## 2. Metrics

### Primary metric (single, pre-committed)
- **Checkout conversion rate** = purchases / checkout-entry sessions.
  This is the one metric the ship decision hinges on. We deliberately did
  **not** pick multiple "primary" metrics — diluting the primary metric is a
  common way teams accidentally p-hack their way to a launch.

### Guardrail metrics (must not regress)
1. **Average order value (AOV)**, conditional on purchase — protects against
   a design that speeds up checkout by pushing users toward smaller baskets
   or discouraging upsell/cross-sell interactions.
2. **14-day refund rate** — protects against a flow that pressures users into
   purchases they later regret (dark-pattern risk).
3. **7-day post-purchase support contact rate** — protects against a flow
   that is faster but more confusing (e.g., unclear error states, hidden
   fees revealed too late).

### Explicitly excluded from the guardrail set (and why)
- **Page load time** was considered but excluded as a formal guardrail
  because the redesign is front-end-only with no backend changes expected to
  affect latency; it is monitored operationally but not statistically
  tested here.
- **Overall revenue per session** was considered as a candidate primary
  metric but rejected in favor of conversion rate: revenue per session
  conflates conversion and basket size into one number, which would make a
  guardrail violation on AOV harder to see if it were offset by higher
  conversion. Keeping them separate gives a clearer diagnostic if something
  goes wrong.

## 3. Power Analysis (a priori)

Computed **before** data collection, using `statsmodels.stats.power.NormalIndPower`.

| Parameter | Value |
|---|---|
| Baseline conversion rate | 6.2% (trailing 90-day average) |
| Minimum detectable effect (MDE) | +8% relative (≈ 6.2% → 6.7%) |
| Statistical power | 80% |
| Significance level (family-wise, before correction) | α = 0.05 |
| Number of formally tested hypotheses | 4 (1 primary + 3 guardrails) |
| Corrected per-test alpha budget (Holm-Bonferroni, worst case) | ≈ 0.0125–0.05 depending on ordering |
| **Required sample size** | **≈ 51,300 sessions per arm** (≈ 102,600 total) |
| Expected daily checkout-entry traffic | ~3,700 sessions/day |
| **Planned test duration** | **28 days** (includes 1 full business cycle to average out day-of-week effects) |

**Why 8% and not smaller:** an MDE below the business-relevant threshold
(product's estimate of the smallest lift worth the engineering cost of
maintaining a new checkout flow) would require an impractically long test
(a 5% MDE would need ~32,000 more sessions/arm and push the test past 6
weeks, colliding with a planned pricing promotion that would confound
results). 8% relative was agreed with Product as the smallest effect worth
detecting.

**Minimum runtime floor:** regardless of when the sample-size target is hit,
the test will run a **minimum of 14 days** to cover at least two full weekly
cycles, since checkout behavior differs materially between weekdays and
weekends.

## 4. Multiple Comparisons Correction

We are formally testing 4 hypotheses against this single experiment (1
primary conversion test + 3 guardrail tests). Testing each independently at
α = 0.05 would inflate the family-wise Type I error rate to
1 − 0.95⁴ ≈ 18.5% — nearly a 1-in-5 chance of a false alarm somewhere in the
family, even if the redesign does nothing.

**Method:** Holm-Bonferroni step-down correction across the family of 4
tests, controlling family-wise error at α = 0.05. Holm-Bonferroni is chosen
over plain Bonferroni because it is uniformly more powerful (fewer false
negatives) while still providing the same strict family-wise error
guarantee — there's no reason to pay the extra conservatism of plain
Bonferroni here.

## 5. Pre-Registered Decision Rule (mechanical, not a judgment call)

```
SHIP the redesign if and only if:
  (a) Primary metric (checkout conversion rate) shows a statistically
      significant INCREASE after Holm-Bonferroni correction, AND
  (b) NONE of the 3 guardrail metrics show a statistically significant
      degradation after the same correction
      (AOV down, refund rate up, or support contact rate up)

Otherwise: HOLD. Do not ship as-is. Root-cause the guardrail regression(s)
and consider a revised design + re-test.
```

This rule is applied programmatically in `scripts/analysis.py::decide_ship()`
so that the final recommendation cannot be adjusted after the fact based on
which way a borderline result happened to break.

## 6. Data Quality Gate: Sample Ratio Mismatch (SRM)

Before any metric is interpreted, we test whether the observed traffic split
matches the intended 50/50 allocation, using a chi-square goodness-of-fit
test. **Threshold: p < 0.001 triggers an SRM flag** (stricter than the usual
0.05 because a false SRM alarm just costs a re-check, while a missed SRM
invalidates every downstream number).

If SRM is detected, the pipeline **halts before computing any metric
p-values** — a mismatched sample can produce a "significant" result driven
entirely by whatever confound caused the mismatch (e.g., a bot filter that
drops more control-arm bot traffic than treatment-arm bot traffic), not by
the treatment itself.

## 7. Novelty / Primacy Effects

Because the redesign changes something users see immediately, we monitor for
a novelty effect: an inflated early effect that fades as the "new checkout"
becomes routine, or the reverse (a fatigue effect where an initially small
effect grows as users learn the new flow). This is treated as a **diagnostic
check, not a formal hypothesis test** — we do not have the sample size to
test day-by-day effects with rigor, and pre-register that we will report this
qualitatively rather than let it change the ship decision.

## 8. Known Limitations (pre-registered)

- Randomization is at the session/cookie level, not the user level — a
  returning user without stable login could theoretically see both arms
  across sessions. Given checkout behavior is typically single-session, this
  risk is accepted rather than engineered around for this test.
- The 28-day window includes one holiday-adjacent weekend; if traffic mix
  looks unusual on manual review, we will note this as a caveat on
  generalizability rather than exclude the days post-hoc.
- Guardrail thresholds are tested for *statistical* significance, not
  pre-registered *practical* significance margins (e.g., a formal
  non-inferiority margin on AOV). This is a known simplification — a more
  mature version of this test would use TOST (two one-sided tests) for
  guardrails instead of a plain two-sided test. Noted here so it isn't
  presented as more rigorous than it is.
