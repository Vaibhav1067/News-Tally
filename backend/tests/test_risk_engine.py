"""Risk engine: every outcome, plus the safety property that the classifier alone never decides."""
from __future__ import annotations

import pytest

from app.services.risk_engine import MatchInput, RiskInput, assess, freshness

T = dict(strong_threshold=0.6, related_threshold=0.4)
FALSEY = {"FALSE": 0.9, "MISLEADING": 0.05, "OUTDATED": 0.05}


def m(verdict, sim, age=100):
    return MatchInput(verdict, sim, age, f"title {verdict}", "Factly")


@pytest.mark.parametrize("verdict,level", [
    ("FALSE", "HIGH MISINFORMATION RISK"), ("MISLEADING", "POTENTIALLY MISLEADING"),
    ("OUTDATED", "POTENTIALLY MISLEADING"), ("TRUE", "EVIDENCE SUPPORTS CLAIM"),
    ("UNVERIFIED", "UNVERIFIED"), (None, "INSUFFICIENT EVIDENCE"),
])
def test_strong_match_verdict_decides(verdict, level):
    out = assess(RiskInput(matches=[m(verdict, 0.8)], class_probabilities=FALSEY, classifier_in_domain=True, **T))
    assert out.level == level


def test_classifier_alone_never_high_risk():
    out = assess(RiskInput(matches=[m("FALSE", 0.2)], class_probabilities={"FALSE": 0.99, "MISLEADING": 0.01},
                           classifier_in_domain=True, **T))
    assert out.level == "UNVERIFIED"
    assert out.evidence_strength_label == "Low"
    assert any("No published fact-check" in x for x in out.missing_evidence)


def test_related_matches_majority_risky():
    out = assess(RiskInput(matches=[m("FALSE", 0.55), m("MISLEADING", 0.5)], **T))
    assert out.level == "POTENTIALLY MISLEADING"


def test_related_matches_true():
    out = assess(RiskInput(matches=[m("TRUE", 0.55)], class_probabilities=FALSEY, classifier_in_domain=True, **T))
    assert out.level == "UNVERIFIED"


def test_short_or_unsupported_is_insufficient():
    out = assess(RiskInput(matches=[], text_too_short=True, **T))
    assert out.level == "INSUFFICIENT EVIDENCE" and out.risk_score == 50.0


def test_score_bounds_and_monotonic():
    lo = assess(RiskInput(matches=[m("TRUE", 0.95)], **T)).risk_score
    mid = assess(RiskInput(matches=[], **T)).risk_score
    hi = assess(RiskInput(matches=[m("FALSE", 0.95)], **T)).risk_score
    assert 0 <= lo < mid < hi <= 100


def test_fact_checker_url():
    out = assess(RiskInput(matches=[], source_is_fact_checker=True, source_known=True, source_name="Factly", **T))
    assert "fact-check published by Factly" in out.summary


def test_freshness():
    assert freshness(0) == 1.0 and freshness(365 * 10) == 0.7 and freshness(None) == 0.85


def test_components_documented():
    out = assess(RiskInput(matches=[m("FALSE", 0.7)], **T))
    assert [c["name"][:8] for c in out.components] == ["Evidence", "Content ", "Source i"]
    assert "Heuristic index" in out.formula
