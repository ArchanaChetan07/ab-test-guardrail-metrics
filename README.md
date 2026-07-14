![CI](https://github.com/ArchanaChetan07/ab-test-guardrail-metrics/actions/workflows/ci.yml/badge.svg)

# Production-Grade A/B Test Guardrails

Decision-grade A/B testing with SRM/data-quality gates, pre-registered metrics, Holm-corrected significance, and mechanical decision rules. The same tested pipeline is applied to three real, independently sourced experiments—none of the underlying experiment data is simulated.

## Three Real Experiments, Three Different Failure Modes

| Case study | Primary metric (treatment vs. control) | Relative difference | `n_users` / exact analysis denominator | Decision | Evidence |
|---|---|---:|---|---|---|
| **Cookie Cats** gate placement | 7-day retention: 18.20% vs. 19.02% | **−4.312%** | **90,189 randomized users** | **DO NOT SHIP — REVERT TO GATE AT LEVEL 30** (significant regression; Holm-adjusted p=0.004663) | [results.json](case_studies/cookie_cats/reports/results.json) · [report](case_studies/cookie_cats/notebooks/cookie_cats_analysis.html) |
| **Udacity** free-trial screener | Gross conversion: 19.832% vs. 21.887% | **−9.391%** | **`n_users` unavailable**: public data are daily aggregates; primary denominator is **34,553 Start Free Trial clicks** across the 23-day evaluation window | **INCONCLUSIVE — HOLD** (net conversion effect unresolved) | [results.json](case_studies/udacity_funnel/reports/results.json) · [report](case_studies/udacity_funnel/notebooks/udacity_funnel_analysis.html) |
| **Website** landing page | Conversion: 11.881% vs. 12.039% | **−1.311%** | **294,478 raw rows → 290,584 cleaned users** used for the primary metric | **DO NOT SHIP — keep old page** (no evidence of improvement; assignment bug detected) | [results.json](case_studies/website_conversion/reports/results.json) · [report](case_studies/website_conversion/notebooks/website_conversion_analysis.html) |

Cookie Cats catches a statistically significant regression. Udacity preserves the honest answer—**“we don't know yet”**—because paying-customer impact remains unresolved. The website study catches **3,893 group/page mismatches (1.322%)** even though raw traffic passes SRM (p=0.892), demonstrating a data-quality bug SRM alone cannot detect. Together, the two user-level datasets contain **384,667 raw records**, while Udacity is correctly reported using its aggregate metric denominator rather than a fabricated user count.

**11/11 tests pass**, including Holm correction against the statsmodels reference and a guardrail test proving SRM failures always block shipping.

```bash
docker compose up --build
# reproduces all three case studies via the shared package (no GitHub Actions notebook run)
```

## Overview

This repo turns “I ran an A/B test in a notebook” into a **decision-grade** analysis path: the same tested Python package powers every case study. Experiments declare metrics in locked `configs/*.json` files, run an SRM gate, test a pre-registered primary + guardrails, apply Holm–Bonferroni, and emit a mechanical ship/no-ship decision.

## Why “Decision-Grade”

Most portfolio A/B demos stop at a single p-value. This framework enforces three rigor signals most demos skip:

1. **SRM gate** — chi-square goodness-of-fit of observed vs expected traffic split (default 50/50). Failures trip at **p < 0.001** (stricter than 0.05) and **always block ship**, even if metrics look great.
2. **Pre-registration** — primary + guardrail metric names live in `configs/*.json` and are validated before results are trusted (no silent post-hoc metric adds).
3. **Holm–Bonferroni** — family-wise correction across the pre-registered metric family at **α = 0.05** via `statsmodels.stats.multitest.multipletests(..., method="holm")`.

## Package Architecture

| Module | Role |
|---|---|
| `abtest_guardrails/srm.py` | `srm_check_counts` — χ² GoF SRM check |
| `abtest_guardrails/metrics.py` | Pre-registration load/validate, z-test, Welch t-test |
| `abtest_guardrails/corrections.py` | Holm–Bonferroni family correction |
| `abtest_guardrails/decision.py` | Mechanical ship rule (**SRM hard-blocks**) |
| `configs/*.json` | Locked metric registries per case study |

Case-study scripts under `case_studies/*/analysis.py` import this package (no duplicated stats logic).

## Guardrail Design

`decide_ship(..., srm_detected=True)` always returns `ship=False` / `srm_blocked=True`, ignoring primary significance.

**Proof:** `tests/test_guardrails.py::TestShipDecision::test_srm_failure_always_blocks_ship`.

## How to Run

### Docker (case-study reproduction)

```bash
docker compose up --build
# writes artifacts/case_study_summary.json
```

Package tests in Docker:

```bash
docker compose --profile test run --rm tests
```

### Local

```bash
python -m venv .venv
# Windows: .\.venv\Scripts\activate
pip install -r requirements.txt
set PYTHONPATH=.
pytest tests/ -v
python scripts/run_case_studies.py
```

Notebook HTML exports remain under `case_studies/*/notebooks/` and root `notebooks/` for reading; **full notebook `nbconvert` re-execution is a local/Docker step, not part of GitHub Actions CI**.

## Tests

```bash
pytest tests/ -v
```

**11 passed** in this session (SRM balanced/mismatch/near-threshold, Holm vs statsmodels, ship rules including SRM hard-block, pre-registration validation).

## Tech Stack

- Python 3.11
- pandas, numpy, scipy, statsmodels
- pytest + GitHub Actions (package tests only)
- Docker / Compose for case-study reproduction

## License

See repository license file if present.
