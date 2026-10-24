"""v6 — NATO/Admiralty (STANAG 2511) derecelendirmesi: kaynak güvenilirliği (A-F) + bilgi
doğruluğu (1-6), ör. "B2".

İstihbarat raporlarının ortak dili bu iki karakterli kod. OsintLab'in kendi ölçüleri zaten var
(Source.reliability, Claim.knowledge_state); bu modül YENİ bir değerlendirme yapmaz, mevcut
deterministik değerleri standart koda ÇEVİRİR. Eşlemenin gerekçesi:

Kaynak (A-F) — `Source.reliability` (kullanıcının verdiği 0-1 değer):
    A ≥ 0.90 tamamen güvenilir · B ≥ 0.75 genellikle güvenilir · C ≥ 0.60 oldukça güvenilir ·
    D ≥ 0.40 genellikle güvenilmez · E < 0.40 güvenilmez · F değerlendirilemez (değer yok).

Bilgi (1-6) — STANAG'ın ölçüsü bağımsız teyittir, confidence formülünün doğrulama bileşeniyle
aynı eksen:
    1 başka bağımsız kaynaklarca teyitli  ← CORROBORATED, HIGH_CONFIDENCE
    2 muhtemelen doğru (kanıtlı, bağımsız teyit yok) ← SUPPORTED
    3 olası (tek kaynak, kanıtsız)        ← REPORTED
    5 ihtimal dışı (çelişiyor)            ← CONTRADICTED
    6 doğruluğu değerlendirilemez          ← OBSERVED, UNKNOWN
4 ("şüpheli") kullanılmıyor: sistemin bir iddiayı çelişki OLMADAN şüpheli sayacak deterministik
bir ölçüsü yok; uydurmak yerine boş bırakılıyor.
"""
from __future__ import annotations

RELIABILITY = {
    "A": "Tamamen güvenilir", "B": "Genellikle güvenilir", "C": "Oldukça güvenilir",
    "D": "Genellikle güvenilmez", "E": "Güvenilmez", "F": "Değerlendirilemez",
}
CREDIBILITY = {
    1: "Teyitli", 2: "Muhtemelen doğru", 3: "Olası", 4: "Şüpheli", 5: "İhtimal dışı", 6: "Değerlendirilemez",
}
_STATE_TO_CREDIBILITY = {
    "HIGH_CONFIDENCE": 1, "CORROBORATED": 1, "SUPPORTED": 2, "REPORTED": 3,
    "CONTRADICTED": 5, "OBSERVED": 6, "UNKNOWN": 6,
}


def source_grade(reliability: float | None) -> str:
    if reliability is None:
        return "F"
    for grade, floor in (("A", 0.90), ("B", 0.75), ("C", 0.60), ("D", 0.40)):
        if reliability >= floor:
            return grade
    return "E"


def info_grade(knowledge_state: str | None) -> int:
    return _STATE_TO_CREDIBILITY.get(knowledge_state or "UNKNOWN", 6)


def code(reliability: float | None, knowledge_state: str | None) -> dict:
    s, i = source_grade(reliability), info_grade(knowledge_state)
    return {"code": f"{s}{i}", "source": s, "source_label": RELIABILITY[s], "info": i, "info_label": CREDIBILITY[i]}
