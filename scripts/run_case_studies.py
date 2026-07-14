#!/usr/bin/env python3
"""Re-run all three case-study analyses and print headline numbers."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    cases = [
        ("cookie_cats", ROOT / "case_studies/cookie_cats/analysis.py"),
        ("udacity_funnel", ROOT / "case_studies/udacity_funnel/analysis.py"),
        ("website_conversion", ROOT / "case_studies/website_conversion/analysis.py"),
    ]
    summary = {}
    for name, path in cases:
        print(f"\n===== {name} =====")
        mod = _load(name, path)
        out = mod.run()
        primary = out.get("primary_metric", {})
        summary[name] = {
            "decision": out.get("decision", {}).get("decision"),
            "relative_diff_pct": primary.get("relative_diff_pct"),
            "n_users": out.get("n_users") or out.get("raw_rows") or out.get("clean_rows"),
        }
    out_path = ROOT / "artifacts" / "case_study_summary.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("\nWrote", out_path)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
