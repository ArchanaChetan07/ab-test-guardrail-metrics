"""Unit tests for abtest_guardrails (SRM, Holm, ship decision)."""

from __future__ import annotations

import pytest
from statsmodels.stats.multitest import multipletests

from abtest_guardrails.corrections import holm_bonferroni
from abtest_guardrails.decision import decide_ship
from abtest_guardrails.metrics import load_preregistration, validate_metric_family
from abtest_guardrails.srm import srm_check_counts


class TestSRM:
    def test_balanced_split_passes(self):
        # Exact 50/50 → chi2 ~ 0, p ~ 1
        out = srm_check_counts(5000, 5000, expected_ratio=0.5, threshold=0.001)
        assert out["srm_detected"] is False
        assert out["p_value"] > 0.05
        assert out["n_total"] == 10000

    def test_clear_mismatch_fails(self):
        # Extreme imbalance: should fail even at p<0.001
        out = srm_check_counts(9000, 1000, expected_ratio=0.5, threshold=0.001)
        assert out["srm_detected"] is True
        assert out["p_value"] < 0.001

    def test_near_threshold_edge(self):
        # Mild imbalance: significant at α=0.05 but not at the project's SRM α=0.001
        out_loose = srm_check_counts(5100, 4900, threshold=0.05)
        out_strict = srm_check_counts(5100, 4900, threshold=0.001)
        assert out_loose["p_value"] == pytest.approx(0.0455, abs=1e-3)
        assert out_loose["srm_detected"] is True
        assert out_strict["srm_detected"] is False


class TestHolm:
    def test_matches_statsmodels_reference(self):
        raw = [
            {"metric": "a", "p_value": 0.01},
            {"metric": "b", "p_value": 0.04},
            {"metric": "c", "p_value": 0.03},
        ]
        alpha = 0.05
        reject_ref, p_adj_ref, _, _ = multipletests(
            [r["p_value"] for r in raw], alpha=alpha, method="holm"
        )
        holm_bonferroni(raw, alpha=alpha)
        for r, rej, padj in zip(raw, reject_ref, p_adj_ref):
            assert r["significant_after_correction"] is bool(rej)
            assert r["p_value_holm_adjusted"] == pytest.approx(float(padj), abs=1e-6)

    def test_hand_verified_vs_statsmodels(self):
        # Known p-vector; ground truth = statsmodels multipletests(method='holm')
        raw = [
            {"metric": "a", "p_value": 0.01},
            {"metric": "b", "p_value": 0.04},
            {"metric": "c", "p_value": 0.03},
        ]
        reject_ref, p_adj_ref, _, _ = multipletests(
            [0.01, 0.04, 0.03], alpha=0.05, method="holm"
        )
        holm_bonferroni(raw, alpha=0.05)
        assert [r["significant_after_correction"] for r in raw] == list(map(bool, reject_ref))
        # Only the smallest p remains significant after Holm at α=0.05 for this set
        assert raw[0]["significant_after_correction"] is True
        assert raw[1]["significant_after_correction"] is False
        assert raw[2]["significant_after_correction"] is False
        assert raw[0]["p_value_holm_adjusted"] == pytest.approx(float(p_adj_ref[0]), abs=1e-6)


class TestShipDecision:
    def _sig_primary(self, diff=0.02):
        return {
            "metric": "primary",
            "absolute_diff": diff,
            "significant_after_correction": True,
            "p_value": 0.001,
        }

    def test_srm_failure_always_blocks_ship(self):
        """CRITICAL: SRM fail cannot be bypassed by significant positive metrics."""
        decision = decide_ship(
            srm_detected=True,
            primary=self._sig_primary(diff=0.05),
            guardrails=[
                {
                    "metric": "g1",
                    "absolute_diff": 0.01,
                    "significant_after_correction": False,
                }
            ],
            primary_desired_direction="positive",
        )
        assert decision["ship"] is False
        assert decision["srm_blocked"] is True
        assert "SRM" in decision["reasons"][0]
        assert decision["decision"].startswith("DO NOT SHIP")

    def test_clean_significant_lift_ships(self):
        decision = decide_ship(
            srm_detected=False,
            primary=self._sig_primary(diff=0.02),
            guardrails=[],
        )
        assert decision["ship"] is True
        assert decision["srm_blocked"] is False

    def test_guardrail_regression_blocks_ship(self):
        decision = decide_ship(
            srm_detected=False,
            primary=self._sig_primary(diff=0.02),
            guardrails=[
                {
                    "metric": "aov",
                    "absolute_diff": -1.5,
                    "significant_after_correction": True,
                }
            ],
        )
        assert decision["ship"] is False
        assert decision["srm_blocked"] is False
        assert any("Guardrail" in r for r in decision["reasons"])

    def test_nonsig_primary_does_not_ship(self):
        decision = decide_ship(
            srm_detected=False,
            primary={
                "metric": "primary",
                "absolute_diff": 0.01,
                "significant_after_correction": False,
                "p_value": 0.2,
            },
        )
        assert decision["ship"] is False


class TestPreregistration:
    def test_cookie_cats_config_loads(self):
        spec = load_preregistration("configs/cookie_cats.json")
        assert spec["primary_metric"]["name"] == "retention_7_primary"
        validate_metric_family(
            spec,
            ["retention_7_primary", "retention_1_guardrail", "game_rounds_guardrail"],
        )

    def test_validate_rejects_extra_metric(self):
        spec = load_preregistration("configs/website_conversion.json")
        with pytest.raises(ValueError, match="do not match"):
            validate_metric_family(spec, ["conversion_rate_primary", "sneaky_extra"])
