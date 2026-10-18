"""Deterministik confidence formülü (Q4) — saf fonksiyon, veritabanı yok."""
import pytest

from app.confidence import compute_confidence


def test_single_source_cannot_reach_supported():
    # Tek kaynaklı bir iddia, kaynak mükemmel olsa bile 0.40'ta kalır — eşik (0.45) tek
    # kaynakla yapısal olarak erişilemez (Faz 16 ölçümünün dayandığı özellik).
    r = compute_confidence(
        source_reliability=1.0, corroborating_source_ids=set(), corroborating_claims_count=0, evidence_count=0
    )
    assert r.confidence == pytest.approx(0.40)
    assert r.knowledge_state == "REPORTED"


def test_saturation_and_full_score():
    r = compute_confidence(
        source_reliability=1.0,
        corroborating_source_ids={"a", "b", "c"},
        corroborating_claims_count=10,
        evidence_count=10,
    )
    assert (r.independence, r.evidence, r.corroboration) == (1.0, 1.0, 1.0)
    assert r.confidence == pytest.approx(1.0)
    assert r.knowledge_state == "HIGH_CONFIDENCE"


def test_contradiction_forces_state_but_keeps_number():
    r = compute_confidence(
        source_reliability=0.9,
        corroborating_source_ids={"a", "b"},
        corroborating_claims_count=3,
        evidence_count=3,
        has_unresolved_contradiction=True,
    )
    assert r.knowledge_state == "CONTRADICTED"
    assert r.confidence > 0.85  # sayı ile etiket ayrı tutulur (Q3)


def test_contradicting_evidence_penalty_is_capped():
    r = compute_confidence(
        source_reliability=1.0, corroborating_source_ids=set(), corroborating_claims_count=0,
        evidence_count=0, contradicting_evidence_count=99,
    )
    assert r.confidence == pytest.approx(0.40 * 0.10)


def test_reliability_is_clamped():
    r = compute_confidence(
        source_reliability=7.0, corroborating_source_ids=set(), corroborating_claims_count=0, evidence_count=0
    )
    assert r.source_quality == 1.0
