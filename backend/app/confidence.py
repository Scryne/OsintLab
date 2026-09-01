"""
Deterministik confidence motoru — Q4 kararı.

"Neden bu confidence?" sorusuna her zaman cevap verilebilmesi gerekiyor (Auditability, madde
55/Design Principle #var). Bu yüzden black-box bir model yerine, her biri ayrı ayrı 0-1
aralığına normalize edilen 4 açıklanabilir alt-skorun ağırlıklı toplamı kullanılır.

Q5 kararı: source reliability (Source.reliability alanı, "geçmiş performans" sinyalini de
temsil eder — ayrı bir "historical_reliability" alanı v1'de tutulmuyor, tek girdi olarak
konsolide edildi) tek başına belirleyici değil, ağırlıklardan sadece biri.

Ağırlıklar (toplamı 1.0):
    source_quality  0.40  — asserting Source'un reliability'si
    independence    0.25  — corroborating claim'lerin FARKLI kaynaklardan gelme oranı
                             (v1 yaklaşımı: distinct source sayısı — tam lineage graph Faz 6'da)
    evidence        0.20  — bağlı Evidence sayısı (normalize)
    corroboration   0.15  — bağımsız olarak doğrulayan claim sayısı (normalize)

Bir claim başka bir claim'le UNRESOLVED şekilde çelişiyorsa (Q9), sayısal confidence yine
hesaplanır ama knowledge_state her zaman CONTRADICTED'a zorlanır — sayı ile durum etiketi
ayrı tutulur (Q3 hibrit model).
"""
from dataclasses import dataclass

SOURCE_QUALITY_WEIGHT = 0.40
INDEPENDENCE_WEIGHT = 0.25
EVIDENCE_WEIGHT = 0.20
CORROBORATION_WEIGHT = 0.15

INDEPENDENCE_SATURATION = 2  # 2+ farklı kaynaktan corroboration -> tam skor
EVIDENCE_SATURATION = 3  # 3+ evidence -> tam skor
CORROBORATION_SATURATION = 3  # 3+ corroborating claim -> tam skor

CONTRADICTING_EVIDENCE_PENALTY_PER_ITEM = 0.30
CONTRADICTING_EVIDENCE_PENALTY_MAX = 0.90

HIGH_CONFIDENCE_THRESHOLD = 0.85
CORROBORATED_THRESHOLD = 0.65
SUPPORTED_THRESHOLD = 0.45


@dataclass
class ConfidenceResult:
    source_quality: float
    independence: float
    evidence: float
    corroboration: float
    confidence: float
    knowledge_state: str


def compute_confidence(
    *,
    source_reliability: float,
    corroborating_source_ids: set[str],
    corroborating_claims_count: int,
    evidence_count: int,
    contradicting_evidence_count: int = 0,
    has_unresolved_contradiction: bool = False,
) -> ConfidenceResult:
    source_quality = max(0.0, min(source_reliability, 1.0))
    independence = min(len(corroborating_source_ids) / INDEPENDENCE_SATURATION, 1.0)
    evidence = min(evidence_count / EVIDENCE_SATURATION, 1.0)
    corroboration = min(corroborating_claims_count / CORROBORATION_SATURATION, 1.0)

    raw_confidence = (
        SOURCE_QUALITY_WEIGHT * source_quality
        + INDEPENDENCE_WEIGHT * independence
        + EVIDENCE_WEIGHT * evidence
        + CORROBORATION_WEIGHT * corroboration
    )

    penalty = min(
        contradicting_evidence_count * CONTRADICTING_EVIDENCE_PENALTY_PER_ITEM,
        CONTRADICTING_EVIDENCE_PENALTY_MAX,
    )
    confidence = round(raw_confidence * (1 - penalty), 4)

    if has_unresolved_contradiction:
        knowledge_state = "CONTRADICTED"
    elif confidence >= HIGH_CONFIDENCE_THRESHOLD:
        knowledge_state = "HIGH_CONFIDENCE"
    elif confidence >= CORROBORATED_THRESHOLD:
        knowledge_state = "CORROBORATED"
    elif confidence >= SUPPORTED_THRESHOLD:
        knowledge_state = "SUPPORTED"
    elif confidence > 0:
        knowledge_state = "REPORTED"
    else:
        knowledge_state = "OBSERVED"

    return ConfidenceResult(
        source_quality=source_quality,
        independence=independence,
        evidence=evidence,
        corroboration=corroboration,
        confidence=confidence,
        knowledge_state=knowledge_state,
    )
