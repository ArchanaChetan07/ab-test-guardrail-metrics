# Product A/B Test Analysis with Guardrail Metrics

Three independent, real-data A/B test case studies, each analyzed with the
same rigorous, reusable pipeline: SRM/data-quality gating, pre-specified
primary + guardrail metrics, multiple-comparisons correction, and a
mechanical ship/no-ship decision rule. **No experiment data here is
simulated** — all three datasets are real, publicly available, and verified
against previously published analyses of the same data.

**Start here:** `reports/executive_summary_all_cases.md`

## The three case studies

| Case study | Real dataset | Data shape | Outcome |
|---|---|---|---|
| `case_studies/cookie_cats/` | Cookie Cats mobile game gate A/B test (90,189 players) | User-level, boolean retention | Significant **regression** — don't ship |
| `case_studies/udacity_funnel/` | Udacity Free Trial Screener (37 days of funnel counts) | Daily-aggregate counts | Genuinely **inconclusive** — hold |
| `case_studies/website_conversion/` | E-commerce landing page test (294,478 users) | User-level, single binary outcome | **Null result** + a real SRM-blind data bug caught |

Each case study folder contains:
```
<case_study>/
├── <dataset>.csv(s)              ← the real, unmodified source data
├── analysis.py                   ← reusable analysis script (SRM, tests, correction, decision)
├── build_notebook.py             ← builds the notebook below
├── notebooks/
│   ├── <case>_analysis.ipynb     ← full narrative walkthrough with charts
│   └── <case>_analysis.html      ← rendered, no-Jupyter-needed version
└── reports/
    ├── results.json               ← machine-readable pipeline output
    └── *.png                      ← exported chart images
```

## Shared methodology

`shared/stats_toolkit.py` is the single source of truth for statistical
methods used across all three case studies:
- `srm_check_counts` — chi-square goodness-of-fit SRM test
- `two_proportion_ztest` — primary/guardrail tests on rate metrics
- `welch_ttest` — guardrail tests on continuous metrics
- `holm_bonferroni` — multiple comparisons correction across a metric family
- `required_sample_size` / `achieved_power` — a priori and retrospective power analysis

Using one shared module (rather than re-deriving statistics per case study)
is deliberate: it's the difference between "I can run a z-test" and "I built
a methodology that holds up across different data shapes."

## How to reproduce any case study

```bash
cd case_studies/<case_study_name>
python3 analysis.py                # runs the pipeline, writes reports/results.json
python3 build_notebook.py           # rebuilds the notebook from scratch
jupyter nbconvert --to notebook --execute --inplace notebooks/*.ipynb
jupyter nbconvert --to html notebooks/*.ipynb
```

Requires: `pandas`, `numpy`, `scipy`, `statsmodels`, `matplotlib`, `jupyter`, `nbconvert`, `nbformat`.

## Where each real dataset came from

- **Cookie Cats**: originally a DataCamp project using Tactile Entertainment's
  actual mobile game A/B test data; mirrored on GitHub
  (`ryanschaub/Mobile-Games-A-B-Testing-with-Cookie-Cats`).
- **Udacity Free Trial Screener**: real experiment run by Udacity, released
  as daily aggregate counts; mirrored on GitHub (`jojoms711/Udacity_AB_Testing`).
- **E-commerce landing page (`ab_data.csv`)**: real website conversion test
  used in numerous "Analyze A/B Test Results" projects; mirrored on GitHub
  (`marooned20/Udacity-AB-testing`).

All three were downloaded and spot-checked against previously published
analyses of the same data (matching totals, matching known conclusions)
before being used here, to confirm authenticity.

## Appendix: pipeline-validation dataset (simulated, not a deliverable)

`data/` and `scripts/` at the project root contain an earlier, **simulated**
checkout-flow dataset with a known injected ground truth, originally built to
validate the analysis pipeline itself (SRM check catches a real SRM bug when
injected; guardrail check catches a real guardrail regression when injected)
before trusting it on the real datasets above. It's kept here for
transparency about how the pipeline was tested, not presented as a fourth
case study. See `data/GROUND_TRUTH.json` and the original `reports/design_doc.md`
/ `reports/executive_summary.md` for that exercise.

## What this project is meant to show in an interview loop

- **Real-data fluency**: sourcing, verifying, and cleaning genuine public
  datasets rather than only working with tidy synthetic examples.
- **Methodological consistency**: one shared statistical toolkit applied
  identically across three different data shapes and three different outcomes.
- **Judgment under ambiguity**: a regression, a genuine "we don't know yet,"
  and a null result — none forced into a false "ship it" story.
- **Data-quality instincts that go beyond SRM**: Case Study 3 specifically
  demonstrates a real bug that a textbook SRM check does not catch.

