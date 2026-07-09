# Executive Summary — Three Real A/B Test Case Studies

This report applies one consistent analysis standard — SRM/data-quality
gating, pre-specified metrics, multiple-comparisons correction, and a
mechanical ship/no-ship rule — to **three real, independently sourced
experiments**, each with a different data shape and a different kind of
"gotcha." None of the underlying experiment data is simulated.

| # | Case study | Data shape | Rows | The "gotcha" it demonstrates |
|---|---|---|---|---|
| 1 | Cookie Cats gate placement | User-level, boolean outcomes | 90,189 | A significant primary-metric **regression** — the tempting change actually makes things worse |
| 2 | Udacity free trial screener | Daily-aggregate funnel counts | 37 days | A genuinely **inconclusive** result that shouldn't be forced into ship/no-ship |
| 3 | E-commerce landing page | User-level, single binary outcome | 294,478 | A **data-quality bug that SRM alone doesn't catch** |

---

## Case Study 1 — Cookie Cats: Ship the change? **No — revert it.**

Moving the game's first progression gate from level 30 to level 40 was
hypothesized to improve retention by letting players build more investment
before hitting a forced wait. The data says the opposite: **7-day retention
dropped significantly** (19.02% → 18.20%, a −4.3% relative change,
Holm-adjusted p ≈ 0.005). This is the case every portfolio needs at least
one of: a real, statistically solid result that says "don't do the thing
that seemed like a good idea."

## Case Study 2 — Udacity Free Trial Screener: Ship? **Hold — inconclusive.**

Adding a screener that filtered out low-commitment free-trial signups worked
exactly as intended on the metric it targeted: **gross conversion dropped
9.4%** (statistically significant, Holm-adjusted p ≈ 0.00001). But the
guardrail metric — net conversion, i.e. actual paying customers — also
dropped (4.1% relative) without reaching significance, and the confidence
interval `[-1.16pp, +0.19pp]` is wide enough that a real revenue cost can't
be ruled out. The honest answer here is **"we don't know yet,"** not a
forced yes or no — and that's presented as the finding, not dressed up as
something more decisive.

## Case Study 3 — Landing Page Redesign: Ship? **No — no evidence it helps.**

Beyond the primary result (new page doesn't beat the old page: 11.88% vs.
12.04%, p = 0.19), this case study exists to make a specific methodological
point: **the raw group sizes passed a standard SRM check almost perfectly**
(50.01/49.99, p = 0.89) — but 1.3% of rows had a genuine group/page
assignment bug that SRM is structurally blind to, because SRM only checks
aggregate counts, not per-user integrity. Catching it required a second,
different check. A portfolio that only runs SRM and calls it "data quality
validated" would have missed this.

---

## What ties these together

The same pipeline (`shared/stats_toolkit.py`) — same SRM logic, same
two-proportion/Welch's-t test functions, same Holm-Bonferroni correction —
was applied to all three, despite three different data shapes (user-level
booleans, daily aggregate counts, user-level single binary outcome) and
three different outcomes (regression, inconclusive, null). That consistency
is the point: the rigor doesn't bend to fit whatever story the data happens
to tell.

## Where to look for the detail

- `case_studies/cookie_cats/notebooks/cookie_cats_analysis.html`
- `case_studies/udacity_funnel/notebooks/udacity_funnel_analysis.html`
- `case_studies/website_conversion/notebooks/website_conversion_analysis.html`
- `shared/stats_toolkit.py` — the common methodology used across all three
