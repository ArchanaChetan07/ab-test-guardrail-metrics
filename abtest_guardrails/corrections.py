"""Multiple-comparison corrections (Holm–Bonferroni)."""

from __future__ import annotations

from typing import Any

from statsmodels.stats.multitest import multipletests


def holm_bonferroni(results: list[dict[str, Any]], alpha: float = 0.05) -> list[dict[str, Any]]:
    """Apply Holm–Bonferroni to a family of metric result dicts (mutates in place).

    Family = the pre-registered primary + guardrail tests for one experiment.
    Uses statsmodels ``multipletests(..., method='holm')`` at family-wise ``alpha``.
    """
    if not results:
        return results
    pvals = [r["p_value"] for r in results]
    reject, p_adj, _, _ = multipletests(pvals, alpha=alpha, method="holm")
    for r, rej, padj in zip(results, reject, p_adj):
        r["p_value_holm_adjusted"] = round(float(padj), 6)
        r["significant_after_correction"] = bool(rej)
    return results
