![CI](https://github.com/ArchanaChetan07/ab-test-guardrail-metrics/actions/workflows/ci.yml/badge.svg)

Decision-grade A/B testing framework — SRM gates, pre-registered metrics, Holm-corrected significance, mechanical ship/no-ship rules. pandas + scipy/statsmodels, tested and Docker-reproducible.

**Cookie Cats:** **−4.312%** relative 7-day retention (19.02% → 18.20%, n=**90,189**, SRM-clean at α=0.001, Holm-corrected) → **DO NOT SHIP** — **11 tests passing**, including a guardrail test proving **SRM failures always block shipping**.

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

## Case Studies

Numbers below were re-run in this session against the checked-in CSVs.

| Study | n / window | Headline | Decision |
|---|---|---|---|
| **Cookie Cats** gate placement | **90,189** users | 7-day retention **19.02% → 18.20%** (**−4.312%** rel.), Holm p≈0.0047 | **DO NOT SHIP** (significant regression) |
| **Udacity** free-trial screener | **23**-day eval window (daily aggregates) | Gross conversion **−9.391%** rel. (Holm sig.); net conversion NS | **INCONCLUSIVE — HOLD** |
| **Website** landing page | **294,478** raw → **290,584** clean | Conversion **−1.311%** rel., p≈0.190; SRM clean but **group/page mismatch** gate failed pre-clean | **DO NOT SHIP** |

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
