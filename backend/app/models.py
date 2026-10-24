from datetime import datetime, timezone
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field


def _to_utc(value: datetime | None) -> datetime | None:
    """Girdi zaman damgasını UTC'ye çevirir; saat dilimi yoksa UTC sayar.

    KùzuDB TIMESTAMP yazarken saat dilimini ÇEVİRMEDEN atıyor: `12:00+03:00` olarak gönderilen
    bir değer `12:00` diye saklanıyor ve okunurken (db.py `_as_utc`) 12:00Z etiketi alıyordu —
    üç saat kayma (2026-10-18 denetiminde gerçek veritabanına karşı ölçüldü). Arayüz zaten UTC
    gönderiyor; bu, API'yi doğrudan çağıran her şey (ajan, script) için aynı garantiyi verir."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _not_blank(value: str) -> str:
    """Boş ya da yalnız boşluktan oluşan metni reddeder (değeri DEĞİŞTİRMEZ — claim metni gibi
    alanların kaynağıyla birebir kalması gerekiyor)."""
    if not value.strip():
        raise ValueError("boş olamaz")
    return value


UtcDatetime = Annotated[datetime, AfterValidator(_to_utc)]
NonBlank = Annotated[str, AfterValidator(_not_blank)]

# Zaman penceresi üst sınırı (gün). Sınırsız değer `now - timedelta(days=…)` hesabını
# OverflowError'la düşürüyordu; zamanlanmış taramada değer saklandığı için HER koşu patlıyordu.
MAX_SINCE_DAYS = 3650


class EntityCreate(BaseModel):
    entity_type: NonBlank = Field(..., examples=["Person", "Organization", "Company", "Location"])
    name: NonBlank
    aliases: list[str] = Field(default_factory=list)


class Entity(EntityCreate):
    id: str
    created_at: datetime


class EntityRelationCreate(BaseModel):
    to_entity_id: str
    relation_type: str = Field(..., examples=["çalışıyor", "sahibi", "ortak", "aile"])
    confidence: float = Field(0.5, ge=0.0, le=1.0)


class RelationCandidateEvidence(BaseModel):
    claim_id: str
    excerpt: str
    # Hangi ad/alias üzerinden eşleşti — Auditability: "neden bu aday" sorusunun cevabı
    # "bir skor" değil, metindeki fiili eşleşme olmalı.
    matched_on: str


class RelationCandidate(BaseModel):
    """Faz 19 — "bu iki entity ilişkili olabilir" önerisi.

    `co_mention_count` ile `shared_event_count` ayrı: biri metinde birlikte anılma (aynı
    haberde iki ad geçebilir, zayıf), diğeri kullanıcının kendi kurduğu ortak olay bağı
    (güçlü). Tek bir skora karıştırılsalardı ikisinin farkı kaybolurdu.

    `relation_type` alanı YOK ve olmayacak: türü sistem tahmin etmez (Design Principle #7)."""

    entity_id: str
    name: str
    entity_type: str
    co_mention_count: int
    shared_event_count: int
    shared_events: list[dict] = Field(default_factory=list)
    evidence: list[RelationCandidateEvidence] = Field(default_factory=list)


class EntityCandidateEvidence(BaseModel):
    claim_id: str
    excerpt: str


class ExtractedEntityCandidate(BaseModel):
    """Faz 20 — claim metninden deterministik olarak çıkarılmış entity adayı.

    `key` normalize edilmiş ad ve kararların kalıcı anahtarı: aday her çağrıda yeniden
    çıkarılır (saklanmaz), saklanan tek şey kullanıcının verdiği karardır.

    `claim_count` ile `source_count` ayrı: tek bir haberde geçen bir özel isim ile beş
    farklı kaynakta geçen bir kurum aynı ağırlıkta olmamalı. Tek skora çevrilmiyorlar —
    Faz 19'daki kararın aynısı."""

    key: str
    name: str
    claim_count: int
    source_count: int
    source_names: list[str] = Field(default_factory=list)
    evidence: list[EntityCandidateEvidence] = Field(default_factory=list)
    status: str = "PENDING"
    promoted_entity_id: str | None = None


class EntityCandidateDismiss(BaseModel):
    """Toplu eleme — Faz 16 kuyruğunun birebir deseni: tekil bir uç bırakılsaydı 79 adaylık
    liste yeni bir darboğaz olurdu."""

    keys: list[str]


class EntityCandidatePromoteItem(BaseModel):
    key: str
    # Ad düzeltilebilir: çıkarma sınır hatası yapmış olabilir ("The New York Times" yerine
    # "New York Times" istenebilir). Boşsa adayın kendi adı kullanılır.
    name: str | None = None
    entity_type: str = "Organization"
    aliases: list[str] = Field(default_factory=list)


class EntityCandidatePromote(BaseModel):
    items: list[EntityCandidatePromoteItem]


class EntityCandidateDecisionResult(BaseModel):
    dismissed: int = 0
    promoted: int = 0
    restored: int = 0
    entities: list[Entity] = Field(default_factory=list)


class RelationPairSide(BaseModel):
    entity_id: str
    name: str
    entity_type: str


class RelationPairEvidence(BaseModel):
    claim_id: str
    excerpt: str
    # "ÖZNE/DEĞME" gibi — hangi tarafın claim'in öznesi, hangisinin yalnızca değdiği.
    # Yön hakkında kullanıcıya fikir verir ama sistem yön ÖNERMEZ.
    kinds: str


class RelationPairCandidate(BaseModel):
    """Faz 22 — graf'ın tamamı için "bu iki entity ilişkili olabilir" önerisi.

    `shared_claim_count` ile `shared_event_count` bilerek ayrı: ilki zayıf (aynı haberde iki
    ad anılmış olabilir), ikincisi güçlü (kullanıcının kendi kurduğu bağ). Tek skora
    karıştırılsalardı fark kaybolurdu. `relation_type` alanı YOK: türü sistem tahmin etmez."""

    a: RelationPairSide
    b: RelationPairSide
    shared_claim_count: int
    shared_event_count: int
    shared_events: list[dict] = Field(default_factory=list)
    evidence: list[RelationPairEvidence] = Field(default_factory=list)


class RelationDecision(BaseModel):
    from_entity_id: str
    to_entity_id: str
    # CREATE | REJECT
    action: str
    # CREATE için zorunlu; REJECT için yok sayılır.
    relation_type: str = ""
    confidence: float = Field(0.5, ge=0.0, le=1.0)


class RelationBatch(BaseModel):
    """Toplu karar — 109 çiftlik bir listede tekil uç bırakmak, Faz 22'yi kendi çözdüğü
    darboğazın bir kopyası yapardı."""

    decisions: list[RelationDecision]


class RelationBatchResult(BaseModel):
    created: int = 0
    rejected: int = 0
    # Aynı türde aktif ilişkisi zaten olan çiftler — ikiz kenar kurulmadı.
    skipped: int = 0


class GraphNode(BaseModel):
    id: str
    # entity | event
    kind: str
    label: str
    entity_type: str
    degree: int = 0
    knowledge_state: str | None = None
    confidence: float | None = None


class GraphEdge(BaseModel):
    source: str
    target: str
    # relation | involved_in | same_as
    kind: str
    label: str


class EntityGraph(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


SAME_AS_STATUSES = ("PENDING", "CONFIRMED", "REJECTED")


class SameAsSuggestRequest(BaseModel):
    to_entity_id: str


class EventCreate(BaseModel):
    title: NonBlank
    event_type: str = Field(..., examples=["saldırı", "seçim", "açıklama", "satın alma"])
    occurred_at: UtcDatetime | None = None
    location: str | None = None


class Event(EventCreate):
    id: str
    knowledge_state: str
    confidence: float
    created_at: datetime


class SourceCreate(BaseModel):
    name: NonBlank
    source_type: str = Field(..., examples=["haber sitesi", "resmi açıklama", "sosyal medya"])
    url: str | None = None
    reliability: float = Field(0.5, ge=0.0, le=1.0)


class Source(SourceCreate):
    id: str
    created_at: datetime


class EvidenceCreate(BaseModel):
    evidence_type: NonBlank = Field(..., examples=["fotoğraf", "video", "belge", "uydu görüntüsü"])
    file_path: str | None = None
    content_hash: str | None = None
    collected_at: UtcDatetime | None = None


class Evidence(EvidenceCreate):
    id: str
    created_at: datetime

    # Faz 15.1 (DOCINT) — belgenin İÇİNE bakmanın sonucu. Hepsi opsiyonel: bir kanıt PDF
    # olmak zorunda değil ve Faz 15.1'den önce yüklenmiş kayıtlarda bu alanlar NULL.
    #
    # `extracted_text` bilerek BURADA YOK: spike'ta tek bir belge 1,65 milyon karakter verdi,
    # bunu her liste yanıtına koymak Evidence Vault sayfasını kullanılamaz hale getirirdi.
    # Tam metin `GET /evidence/{id}/text` ucundan alınıyor.
    extraction_status: str | None = None
    extraction_status_label: str | None = None
    page_count: int | None = None
    pages_done: int | None = None
    extraction_error: str | None = None
    extracted_at: datetime | None = None
    # Faz 15.4 — metnin kaynağı: "extracted" (belgenin kendi metin katmanı) ya da "ocr"
    # (görüntüden tahmin). OCR çıktısı çıkarılmış metinle aynı güvenilirlikte DEĞİLDİR.
    text_source: str | None = None
    ocr_confidence: float | None = None
    ocr_lang: str | None = None


class EvidenceExtraction(BaseModel):
    """Faz 15.1 — bir belgenin çıkarma sonucunun tam hali (`GET /evidence/{id}/extraction`).

    `status` ve `status_label` birlikte dönüyor: kod makine için, etiket insan için. Faz 11'in
    tekrar eden dersi, sistemin yaptığı şeyi söyleyebilmesiydi — arayüze ham `NO_TEXT_LAYER`
    göndermek o dersi unutmak olurdu."""

    evidence_id: str
    status: str | None = None
    status_label: str | None = None
    page_count: int | None = None
    pages_done: int | None = None
    error: str | None = None
    extracted_at: datetime | None = None
    # Belge metadata'sı — Q22: bu alanlar GÜVENİLMEYEN VERİ. Faz 15 spike'ı `/Subject`
    # alanına gömülmüş talimat-görünümlü bir ifadenin buraya aynen geldiğini doğruladı.
    metadata: dict[str, str] = Field(default_factory=dict)
    text_chars: int = 0
    text_preview: str = ""
    text_source: str | None = None
    ocr_confidence: float | None = None
    ocr_lang: str | None = None
    # Faz 15.2 (Q22): belgede/metadata'da bulunan talimat-görünümlü ifadeler. Boş liste
    # "temiz" demek değil, "bilinen desenlerden hiçbiri eşleşmedi" demek — asıl koruma
    # tespit değil, bu metnin hiçbir katmanda komut olarak yürütülmemesi.
    injection_hits: list[dict] = Field(default_factory=list)


class ObservationFromEvidence(BaseModel):
    """Faz 15.2 — bir gözlem bir belgeden geldiyse hangi belgenin hangi sayfalarından
    geldiği. "Hangi belgeden" tek başına yetmez: bir iddianın 492 sayfalık raporun neresinden
    çıktığı kaybolursa kanıt zinciri kopar."""

    evidence_id: str
    page_from: int
    page_to: int
    file_name: str | None = None


class FingerprintField(BaseModel):
    """Faz 15.3 — belge metadata'sının tek bir alanı.

    **Q22: `value` güvenilmeyen veridir.** Belgeyi kim üretmişse o yazmıştır; spike bir
    `/Subject` alanında gerçek bir talimat denemesi doğruladı. Gösterilir, yorumlanmaz."""

    field: str
    value: str
    # Yalnızca kişi/kuruma işaret edebilecek alanlar Entity'ye bağlanabilir. `Creator`/
    # `Producer` yazılım adı taşır; onları bağlanabilir yapmak grafı yazılım adlarıyla
    # kirletirdi.
    linkable: bool = False
    # Alanın kendi başına söylemediği ama çıkarılabilen bilgi — ör. tarih damgasındaki
    # saat dilimi farkı, belgeyi üreten makinenin coğrafi konumuna dair ipucu.
    note: str | None = None


class FingerprintGroup(BaseModel):
    key: str
    label: str
    fields: list[FingerprintField]


class FingerprintLink(BaseModel):
    """Bir metadata alanı ile graf'taki bir Entity arasında kullanıcının kurduğu bağ."""

    entity_id: str
    entity_name: str
    entity_type: str
    field: str
    value: str


class FingerprintLinkCreate(BaseModel):
    field: str = Field(..., examples=["Author", "Company"])


class EvidenceFingerprint(BaseModel):
    """`GET /evidence/{id}/fingerprint` — belgenin üretildiği ortamın izi.

    Belgenin İÇERİĞİ değil: kim yazdı, hangi araçla, ne zaman, hangi kurumun sisteminden
    geçti. Faz 15 spike'ı bunun ölçülebilir değerini gösterdi (NIST belgesinde
    `/Author: Joint Task Force`, `/Creator: Acrobat PDFMaker`, bir SharePoint
    `/ContentTypeId` GUID'i)."""

    evidence_id: str
    groups: list[FingerprintGroup] = Field(default_factory=list)
    links: list[FingerprintLink] = Field(default_factory=list)
    # Metadata alanlarında bulunan talimat-görünümlü ifadeler (yalnızca metadata kaynaklı
    # olanlar — belge metnindekiler `EvidenceExtraction.injection_hits` içinde).
    injection_hits: list[dict] = Field(default_factory=list)


class EvidenceObservationCreate(BaseModel):
    """Belgenin bir sayfa aralığından gözlem üretme isteği (1 tabanlı, `page_to` dahil)."""

    page_from: int = Field(1, ge=1)
    page_to: int = Field(1, ge=1)


class EvidenceVaultItem(Evidence):
    """Faz 13 — Evidence Vault listesi için zenginleştirilmiş kanıt.

    `has_file` SAKLANAN bir alan değil, her okumada hesaplanıyor: `file_path` dolu olsa bile
    dosya yerinde olmayabilir (elle girilmiş bir yol ya da taşınmış/silinmiş bir dosya).
    Bunu göstermemek, indirilemeyen bir kanıtı indirilebilir gibi sunmak olurdu.

    `linked_claims` ise Faz 13'te ortaya çıkan bir boşluğu kapatıyor: Evidence-[:SUPPORTS|
    CONTRADICTS]->Claim kenarları Faz 10'dan beri yazılabiliyor ve confidence hesabında
    sayılıyordu, ama hiçbir uç onları listelemiyordu — "bu kanıt neyi destekliyor" sorusu
    yalnızca claim'in confidence'ı üzerinden dolaylı olarak cevaplanabiliyordu."""

    has_file: bool
    linked_claims: list[dict] = Field(default_factory=list)


class EvidenceClaimLink(BaseModel):
    stance: str = Field(..., examples=["SUPPORTS", "CONTRADICTS"])


class ClaimCreate(BaseModel):
    text: NonBlank
    source_id: NonBlank
    # Faz 11 (dogfooding F12): iddianın GEÇERLİLİK başlangıcı — kayıt anı değil. Verilmezse
    # "şimdi"ye düşer. Arşivden toplanan eski bir haber bugün kaydedilse bile temporal
    # sıralama (supersede) yayın tarihine göre yapılmalı, toplama anına göre değil.
    valid_from: UtcDatetime | None = None
    about_entity_id: str | None = None
    about_event_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(
        default_factory=list,
        description="Bu claim'i CONTRADICTS eden Evidence id'leri (stance parametresi, confidence.py ceza dalı)",
    )
    corroborates: list[str] = Field(
        default_factory=list, description="Bu claim'in bağımsız olarak doğruladığı diğer claim id'leri (Q4 corroboration girdisi)"
    )
    contradicts: list[str] = Field(
        default_factory=list, description="Bu claim'in çeliştiği diğer claim id'leri (Q9 Contradiction)"
    )
    supersedes: str | None = Field(
        None, description="Bu claim'in temporal olarak yerini aldığı eski claim id'si (Q9 temporal versiyonlama)"
    )


class Claim(BaseModel):
    id: str
    text: str
    source_id: str
    # Faz 11 (dogfooding F17): bu iki alan ClaimCreate'te KABUL ediliyordu ve `_claim_about()`
    # helper'ı zaten okuyordu, ama yanıta hiç konmuyordu — yazılabilen ama okunamayan bir bağ.
    # Sonuç: arayüz "bu claim bir entity'ye bağlı mı" sorusunu cevaplayamıyordu.
    about_entity_id: str | None = None
    about_event_id: str | None = None
    knowledge_state: str
    confidence: float
    valid_from: datetime
    valid_to: datetime | None
    # Faz 11 (tarama bulgusu F34): SUPERSEDES kenarı yazılıyor ve `valid_to` set ediliyordu,
    # ama kenar HİÇBİR yerde okunmuyor ve `valid_to`'yu hiçbir sorgu filtrelemiyordu. Sonuç:
    # yerini almış (eskimiş) bir claim, entity sayfasında/timeline'da/vault'ta güncel olanla
    # birebir aynı görünüyordu — Faz 2'nin "temporal supersede" kriteri depolamada vardı,
    # kullanıcının gördüğü hiçbir şeyde yoktu.
    superseded_by_claim_id: str | None = None
    supersedes_claim_id: str | None = None
    created_at: datetime
    updated_at: datetime


class ObservationCreate(BaseModel):
    raw_content: NonBlank
    observed_at: UtcDatetime | None = None
    source_url: str | None = Field(
        None, description="Bu observation bir collector tarafından toplandıysa kaynak URL — provenance (Q22/Data Provenance)"
    )


class Observation(ObservationCreate):
    id: str
    promoted: bool
    created_at: datetime
    # Faz 11 (dogfooding F32): `promoted` yalnızca confidence EŞİĞİNİ GEÇEN durumu işaretler.
    # Eşiği geçmeyen bir promote de bir Claim üretir (ve o claim graf'ta, entity sayfasında,
    # vault'ta durur) ama observation `promoted=false` kalır. Bu alan olmadan arayüz "hiç
    # işlenmemiş" ile "işlendi, eşiği geçmedi"yi ayırt edemiyordu: Promote butonu duruyor,
    # tekrar basılınca 409 geliyordu.
    produced_claim_id: str | None = None
    # Faz 15.2 — belgeden gelen gözlemler için provenance. Collector'dan gelenlerde None
    # (onların provenance'ı `source_url`); belge tabanlı gözlemlerin URL'i YOKTUR, o yüzden
    # source_url'e uydurma bir değer yazmak yerine ayrı bir alan kullanılıyor.
    from_evidence: ObservationFromEvidence | None = None
    # Faz 15.2 (Q22) — bu gözlemin KENDİ metninde bulunan talimat-görünümlü ifadeler.
    # Kaynağı belge de olabilir collector da: toplanan hiçbir metin talimat değildir.
    injection_hits: list[dict] = Field(default_factory=list)
    # Faz 15.4 — metnin kaynağı: "extracted" (belgenin kendi metin katmanı) ya da "ocr"
    # (görüntüden tahmin). İşaret metinle BİRLİKTE seyahat ediyor, çünkü promote kararı bu
    # gözlem üzerinde veriliyor — 15.2'de injection uyarısı için öğrenilen dersin aynısı.
    text_source: str | None = None
    # Faz 16 — "değerlendirildi, bilgiye dönüştürülmedi". `promoted=false` tek başına iki
    # ayrı hâli anlatmak zorundaydı: "henüz bakılmadı" ve "bakıldı, yükseltilmedi". 223
    # kayıtlık bir kuyrukta bu ayrım olmadan ilerleme ölçülemiyor — elenen gözlem ertesi gün
    # yine kuyruğun içinde duruyor. Kayıt SİLİNMEZ (Q17: yükselmeyen şey de kaybolmaz).
    dismissed: bool = False
    dismissed_at: datetime | None = None
    dismiss_reason: str | None = None


INVESTIGATION_STATUSES = ("OPEN", "ACTIVE", "PAUSED", "RESOLVED", "CLOSED", "ARCHIVED")

# Q16 durum makinesi. ARCHIVED terminaldir (v1'de yeniden açılmaz).
INVESTIGATION_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "OPEN": ("ACTIVE", "ARCHIVED"),
    "ACTIVE": ("PAUSED", "RESOLVED", "ARCHIVED"),
    "PAUSED": ("ACTIVE", "ARCHIVED"),
    "RESOLVED": ("ACTIVE", "CLOSED", "ARCHIVED"),
    "CLOSED": ("ARCHIVED",),
    "ARCHIVED": (),
}


class InvestigationCreate(BaseModel):
    title: NonBlank
    research_question: str


class Investigation(InvestigationCreate):
    id: str
    status: str
    # Faz 13 (madde 30) — Workspace zincirinin son iki adımı: "Analysis" analistin yürüttüğü
    # muhakeme, "Conclusion" araştırmanın cevabı. Bunlar olmadan bir investigation, cevabı
    # hiçbir yere yazılmadan kapatılabiliyordu; Research Question vardı, karşılığı yoktu.
    analysis: str | None = None
    conclusion: str | None = None
    concluded_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class InvestigationNarrativeUpdate(BaseModel):
    """Analysis ve/veya Conclusion'ı yazar. İkisi de opsiyonel — analiz araştırma sürerken
    büyüyen bir metin, sonuç ise sonda yazılıyor."""

    analysis: str | None = None
    conclusion: str | None = None


class InvestigationTransition(BaseModel):
    to_status: str = Field(..., examples=list(INVESTIGATION_STATUSES))


class HypothesisCreate(BaseModel):
    text: NonBlank = Field(..., examples=["H1: Company X is directly controlled by Organization Y."])


class Hypothesis(HypothesisCreate):
    id: str
    status: str
    created_at: datetime


class HypothesisEvidenceLink(BaseModel):
    evidence_id: str
    stance: str = Field(..., examples=["SUPPORTS", "WEAKENS", "REFUTES"])


class SignalReason(BaseModel):
    """Bir gözlemin kuyrukta neden yukarıda/aşağıda olduğunun tek bir gerekçesi.

    Skor tek bir sayı olarak dönseydi kuyruk bir kara kutu olurdu: kullanıcı 180 kaydı
    toplu elerken neye güvendiğini bilemezdi. Faz 12'nin `_matching_entities` kararındaki
    aynı disiplin — deterministik, LLM'siz, ve hangi ad üzerinden eşleştiği görünür."""

    code: str
    text: str
    weight: float


class QueueItem(Observation):
    """Kuyruk satırı: gözlemin kendisi + neden bu sırada olduğu + kısa yol için öneriler."""

    signal_score: float
    signal_reasons: list[SignalReason] = Field(default_factory=list)
    matched_entities: list[dict] = Field(default_factory=list)
    # Hızlı promote'un "önerilir, kullanıcı onaylar" tarafı (Design Principle #7): sistem
    # kaynağı ve entity bağını ÖNERİR, kararı vermez.
    suggested_source_id: str | None = None
    suggested_source_name: str | None = None
    suggested_entity_id: str | None = None
    host: str | None = None
    age_days: int = 0


class QueueHostBucket(BaseModel):
    """Kuyruğun kaynak-adresine göre dağılımı — toplu eleme kararı pratikte bu eksende
    veriliyor ("bu feed'in tamamı ilgisiz")."""

    host: str
    count: int
    high_signal: int


class QueueStats(BaseModel):
    """Kuyruk sağlığı. Roadmap'in Faz 16 maddesi: '221 rakamı ancak API'ye elle sorulunca
    çıktı' — bu sayıların arayüzde görünür olması fazın bitti kriterinin bir parçası."""

    pending: int
    dismissed: int
    evaluated: int
    total: int
    high_signal: int
    noise: int
    oldest_pending_at: datetime | None = None
    oldest_pending_age_days: int | None = None
    hosts: list[QueueHostBucket] = Field(default_factory=list)


class ObservationQueue(BaseModel):
    stats: QueueStats
    items: list[QueueItem] = Field(default_factory=list)
    matched: int = Field(
        0, description="Filtreden geçen toplam gözlem sayısı (items sayfalanmış olabilir)"
    )
    high_signal_threshold: float


class ObservationDismiss(BaseModel):
    """Toplu eleme. Tekil bir uç değil, çünkü darboğazın kendisi tekillikti."""

    observation_ids: list[str]
    reason: str | None = None


class ObservationDismissResult(BaseModel):
    dismissed: int
    # Zaten claim üretmiş ya da bulunamamış gözlemler sessizce yutulmaz.
    skipped: list[str] = Field(default_factory=list)


class ObservationPromoteBatch(BaseModel):
    """Faz 16 (ikinci tur) — seçilen gözlemleri TEK kararla promote eder.

    **Neden var.** İlk turda kuyruk toplu ELEMEYİ ucuzlattı ama promote kayıt başına kaldı:
    gerçek kuyrukta 21 tanesi aynı kaynağa (`openai.com` resmi duyuruları) ve aynı entity'ye
    (OpenAI) bağlanacaktı, yani aynı iki alan 21 kez onaylanacaktı. Bu, kapatılmaya çalışılan
    darboğazın küçültülmüş hali — kullanıcının ilk kullanımda söylediği de tam olarak buydu.

    **Design Principle #7 ile çelişmiyor.** Bu otomatik bir kural değil: kullanıcı kümeyi
    kendisi seçiyor, gördüğü kayıtlar için bir kez karar veriyor. Roadmap'in Faz 16 maddesinin
    kendi argümanı — "bir kuralı bir kez tanımlamak da insanın kontrolüdür, 221 kez tıklamak
    da" — burada kural yazmadan, doğrudan seçime uygulanıyor."""

    observation_ids: list[str]
    source_id: str | None = Field(
        None,
        description="Tüm kümeye uygulanacak kaynak. None ise her gözlem KENDİ önerisini kullanır "
        "(adresi hangi Source'un adresiyle aynı host'ta).",
    )
    about_entity_id: str | None = Field(
        None, description="Tüm kümeye uygulanacak entity. None ise her gözlem kendi önerisini kullanır."
    )
    require_entity: bool = Field(
        True,
        description="Entity bağı çözülemeyen gözlemi promote ETME, atla. Faz 11'in F15/F16 dersi: "
        "bağsız claim yalıtık kalır (Memory Recall bulamaz, vault notunda görünmez) ve bu, "
        "toplu bir işlemde sessizce onlarca kayda birden olur.",
    )


class ObservationPromoteBatchItem(BaseModel):
    observation_id: str
    # PROMOTED (eşiği geçti) / BELOW_THRESHOLD (claim üretildi, eşiğin altında) / SKIPPED.
    # Üçü ayrı, çünkü ikincisi bir hata değil — Q1'in katmanlı hafıza modelinin normal sonucu.
    status: str
    headline: str
    claim_id: str | None = None
    confidence: float | None = None
    message: str | None = None


class ObservationPromoteBatchResult(BaseModel):
    """Toplu işlemin sonucu kayıt kayıt dönüyor: 21 kaydın 3'ü atlandıysa hangileri olduğu
    söylenmezse kullanıcı kuyruğa dönüp aradaki farkı kendi bulmak zorunda kalırdı."""

    promoted: int
    below_threshold: int
    skipped: int
    items: list[ObservationPromoteBatchItem] = Field(default_factory=list)


class ObservationPromote(BaseModel):
    source_id: str
    about_entity_id: str | None = None
    about_event_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    corroborates: list[str] = Field(default_factory=list)
    # Faz 11 (dogfooding F26): bu iki alan yoktu. `create_claim` ikisini de destekliyordu ama
    # promote geçirmiyordu — ve promote, toplanan veriden Claim'e giden TEK yol. Sonuç:
    # collector'dan gelen hiçbir claim asla çelişkili işaretlenemiyordu, yani confidence.py'nin
    # `has_unresolved_contradiction` dalı ve CONTRADICTED durumu bu boru hattı için ölü koddu.
    contradicts: list[str] = Field(
        default_factory=list, description="Bu claim'in çeliştiği diğer claim id'leri (Q9)"
    )
    supersedes: str | None = Field(
        default=None, description="Bu claim'in yerini aldığı eski claim id'si (Q9 temporal)"
    )


class CandidateClaim(BaseModel):
    """Aday listesinde bir claim'in gösterilmesi için gereken minimum. Tam `Claim` değil —
    liste 200 çift dönebiliyor ve her çift iki claim taşıyor."""

    id: str
    text: str
    source_id: str
    source_name: str
    confidence: float
    knowledge_state: str
    valid_from: datetime


class CorroborationCandidate(BaseModel):
    """Faz 17 — "bu iki claim aynı olayı anlatıyor" adayı.

    `kind` bu fazın en önemli alanı: aynı ölçüm üç farklı sonuca çıkabiliyor ve ikisi
    bağlanmamalı.
    - `CORROBORATION`: bağımsız kaynaklar, aynı olay, farklı yazım — confidence'ı yükseltir.
    - `DERIVED_SUSPECT`: kaynaklar farklı ve lineage'da bağlı DEĞİLLER, ama metin neredeyse
      aynı. Muhtemelen henüz işaretlenmemiş bir syndication — önce kaynak türetmesi kurulmalı.
    - `SHARED_ROOT`: Source'lar farklı ama DERIVED_FROM zinciri ikisini de aynı köke
      indiriyor. Kullanıcının "iki farklı site, demek ki iki kaynak" diye okuması en olası
      yer burası ve bu okuma confidence'ı sahte yükseltirdi (Q6, Faz 6).
    - `SAME_SOURCE_DUPLICATE`: aynı kaynağın aynı haberi iki kez kaydedilmiş hali.
    Son üçünü "iki kaynak" sanıp bağlamak confidence'ı SAHTE yükseltirdi; bu fazın önlemesi
    gereken asıl hata bu — API bu yüzden yalnızca uyarmıyor, doğrulama bağını REDDEDİYOR."""

    claim_a: CandidateClaim
    claim_b: CandidateClaim
    kind: str
    rare_overlap: float
    text_similarity: float
    days_apart: float
    shared_terms: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    # Bağlanırsa confidence nereye gider — bu fazın var olma sebebi tam olarak bu hareket.
    projected_a: float | None = None
    projected_b: float | None = None


class ObservationCorroborationCandidate(BaseModel):
    """Faz 28 — "bu doğrulanmamış claim'i şu ham gözlem doğrulayabilir" adayı.

    Faz 17'nin claim ↔ claim adayının gözlem tarafındaki karşılığı. `kind` aynı disiplini
    taşıyor: yalnızca CORROBORATION bağlanmaya değer, geri kalan üçü UYARIDIR ve bağlanırsa
    confidence sahte yükselir. Fark şu: burada bağlamak demek gözlemi promote etmek demek,
    yani grafta yeni bir claim doğuyor — bu yüzden `promote_hint` alanı öneriyi hazır
    taşıyor, kullanıcı formu yeniden doldurmasın diye."""

    claim_id: str
    claim_text: str
    claim_source_name: str | None = None
    claim_confidence: float | None = None
    claim_knowledge_state: str | None = None
    # Promote formunu önceden doldurmak için: doğrulayan claim, doğrulanan claim'le AYNI
    # şey hakkında olmalı. Kullanıcıya bunu yeniden seçtirmek, Faz 16'nın kapattığı
    # "kararın pahalı olması" sorununu burada yeniden açardı.
    claim_about_entity_id: str | None = None
    claim_about_event_id: str | None = None

    observation_id: str
    observation_text: str
    observation_url: str | None = None
    observation_host: str | None = None
    observation_dismissed: bool = False

    kind: str
    rare_overlap: float
    text_similarity: float
    days_apart: float
    shared_terms: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    suggested_source_id: str | None = None
    suggested_source_name: str | None = None
    # Bağlanırsa claim'in confidence'ı nereye gider. Faz 17'deki gerekçenin aynısı: hareket
    # görünmezse kullanıcı neden uğraştığını bilmez.
    projected_confidence: float | None = None


class ClaimLinkRequest(BaseModel):
    claim_a_id: str
    claim_b_id: str
    # CORROBORATES (birbirini doğrular) | CONTRADICTS (çelişir). Aynı aday listesinden ikisi
    # de kurulabilmeli: aynı olayı anlatan iki claim doğrulayabileceği gibi çelişebilir de,
    # ayrı ekranlar olsaydı kullanıcı aynı çifti iki kez bulmak zorunda kalırdı.
    link: str = "CORROBORATES"


class ClaimLinkBatch(BaseModel):
    """Toplu bağlama — Faz 16'nın birebir dersi: tekil bir uç bırakılsaydı bu fazın kendisi
    yeni bir darboğaz olurdu."""

    pairs: list[ClaimLinkRequest]


class ClaimLinkResult(BaseModel):
    claim_a_id: str
    claim_b_id: str
    link: str
    # LINKED | SKIPPED
    status: str
    message: str | None = None
    # Bağlantının gerçek etkisi (tahmin değil, yeniden hesaplanmış değer).
    confidence_before: dict[str, float] = Field(default_factory=dict)
    confidence_after: dict[str, float] = Field(default_factory=dict)
    state_after: dict[str, str] = Field(default_factory=dict)


class ClaimLinkBatchResult(BaseModel):
    linked: int
    skipped: int
    results: list[ClaimLinkResult] = Field(default_factory=list)


class ClaimContradictionAdd(BaseModel):
    """Faz 11 (dogfooding F26): çelişki YALNIZCA claim oluşturulurken kurulabiliyordu; sonradan
    eklemenin hiçbir yolu yoktu. Bu, F16'nın (about bağı sonradan düzeltilemiyordu) birebir
    kardeşi — ve gerçek araştırma bu sırayla ilerlemiyor: çelişen ikinci haber, ilk claim
    kaydedildikten günler sonra çıkıyor.

    History Is Immutable ile çelişmez: iki claim'in METNİ de değişmiyor, aralarına yalnızca
    bir ilişki ekleniyor ve ikisinin de confidence'ı yeniden hesaplanıyor."""

    other_claim_id: str


class ClaimSupersedeAdd(BaseModel):
    """Faz 11 (F45): supersede sonradan da bildirilebilmeli — gerçek araştırmada yeni bilgi,
    eskisi kaydedildikten sonra çıkıyor ve bazen eskisi SONRADAN kaydediliyor."""

    supersedes_claim_id: str


class ClaimAboutUpdate(BaseModel):
    """Faz 11 (dogfooding F16): bir claim'in hangi entity/event hakkında olduğu, claim
    oluştuktan SONRA da düzeltilebilmeli. Promote sırasında bu alan atlanırsa claim graf'ta
    yalıtık kalıyordu ve onarmanın hiçbir yolu yoktu (PATCH/DELETE ucu yok, promote ise
    idempotent olduğu için 409 veriyor).

    History Is Immutable ilkesiyle çelişmez: claim'in METNİ (kaynağın iddiası) değişmiyor,
    yalnızca sınıflandırması — neyle ilgili olduğu — düzeltiliyor."""
    about_entity_id: str | None = None
    about_event_id: str | None = None


class MentionCandidate(BaseModel):
    entity_id: str
    name: str
    entity_type: str
    # Hangi ad/alias üzerinden eşleşti — Auditability: "neden bu öneri" sorusunun cevabı bir
    # skor değil, metindeki fiili eşleşme olmalı. Faz 20'nin alias kararları buraya akıyor
    # ("GPT-6 Astra" -> Astra), yani eşleşme adın kendisi olmayabilir.
    matched_on: str


class ClaimMentionGroup(BaseModel):
    """Faz 21 — bir claim'in DEĞDİĞİ entity adayları, claim ekseninde gruplanmış.

    Gruplama claim başına, çünkü karar orada ucuz: metne bir kez bakıp "evet bu üçü de
    geçiyor" demek, aynı üç çifti üç ayrı satırda değerlendirmekten hızlıdır (Faz 16)."""

    claim_id: str
    text: str
    knowledge_state: str
    confidence: float
    source_name: str | None = None
    # Claim'in ÖZNESİ — aday değil, bağlam. Kullanıcı "bu claim zaten OpenAI hakkında"
    # bilgisini görmeden Microsoft'un bir değme mi yoksa özne mi olduğuna karar veremez.
    subject_name: str | None = None
    candidates: list[MentionCandidate] = Field(default_factory=list)


class MentionDecision(BaseModel):
    claim_id: str
    entity_id: str
    # CONFIRM | REJECT
    action: str
    matched_on: str = ""


class MentionBatch(BaseModel):
    """Toplu karar — Faz 16/17/20'nin aynı dersi: tekil bir uç bırakılsaydı 129 çiftlik liste
    yeni bir darboğaz olurdu."""

    decisions: list[MentionDecision]


class MentionBatchResult(BaseModel):
    confirmed: int = 0
    rejected: int = 0


class ClaimMention(BaseModel):
    entity_id: str
    name: str
    entity_type: str
    matched_on: str


class MentionedInClaim(BaseModel):
    claim_id: str
    text: str
    knowledge_state: str
    confidence: float
    created_at: datetime
    matched_on: str
    subject_entity_id: str | None = None
    subject_entity_name: str | None = None
    about_event_id: str | None = None
    about_event_title: str | None = None


class LineageLinkRequest(BaseModel):
    """Faz 11 (dogfooding F23): iki kaynak arasındaki DERIVED_FROM ilişkisini ELLE kurmak.

    Otomatik tespit (POST /sources/lineage/detect) metin benzerliğine dayanıyor ve gerçek
    veride yalnızca metni birebir kopyalayan yayıncılarda çalışıyor; olayı kendi cümleleriyle
    yeniden yazan yayıncılarda similarity 0.0 çıkıyor. Design Principle #7 gereği son karar
    zaten insanda — bu, insanın kararını graf'a yazabilmesini sağlıyor."""
    upstream_source_id: str = Field(..., description="Bu kaynağın TÜRETİLDİĞİ (daha önceki/orijinal) Source")
    note: str | None = Field(None, description="Kullanıcının gerekçesi (denetlenebilirlik için saklanır)")


class LineageDetectRequest(BaseModel):
    claim_id_a: str = Field(..., description="Daha erken (upstream/orijinal) olduğu varsayılan claim — created_at otomatik karşılaştırılır")
    claim_id_b: str = Field(..., description="İkinci claim — hangisinin daha erken olduğu created_at'e göre otomatik belirlenir")


class AllowlistAdd(BaseModel):
    hostname: str = Field(..., examples=["feeds.bbci.co.uk"], description="Tam eşleşme ile kontrol edilir (subdomain dahil edilmez)")


class CollectorFetchRequest(BaseModel):
    url: str
    mode: str = Field(..., examples=["rss", "web", "telegram"])
    # Faz 11 (dogfooding F2): bazı feed'ler tüm arşivi yayınlıyor (ör. openai.com/news:
    # 1164 item). Limitsiz tarama sistemi tek hamlede kullanılamaz hale getiriyordu.
    limit: int = Field(default=50, ge=1, le=500)
    # Opsiyonel zaman penceresi: sadece son N günde yayınlanmış item'ları al.
    since_days: int | None = Field(default=None, ge=1, le=MAX_SINCE_DAYS)


# --- Faz 26: kanıt katmanı (arşiv) ---------------------------------------

class ArchiveRecord(BaseModel):
    """Bir claim'in dayandığı içeriğin arşiv kopyası."""

    evidence_id: str
    claim_id: str
    archive_url: str | None = None
    archive_status: str
    archive_status_label: str
    archive_match: float | None = None
    archive_checked_at: datetime | None = None
    archive_note: str | None = None
    content_hash: str | None = None
    collected_at: datetime | None = None
    # Arşivin ait olduğu iddia. Başlık listede zorunlu: hash listesi kimseye bir şey söylemez.
    claim_headline: str | None = None
    claim_state: str | None = None
    claim_confidence: float | None = None
    # Skora GİRİYOR mu — arşivin varlığından ayrı bir soru. Yalnızca canlı sayfaya karşı
    # doğrulanmış arşivler SUPPORTS kenarı kurar (bkz. app/archive.py).
    scored: bool = False


class ArchiveBatchRequest(BaseModel):
    # Boş bırakılırsa arşivi olmayan TÜM claim'ler işlenir (geri doldurma).
    claim_ids: list[str] | None = None


class ArchiveBatchItem(BaseModel):
    claim_id: str
    action: str  # "olusturuldu" | "zaten_var" | "atlandi"
    evidence_id: str | None = None
    archive_status: str | None = None
    reason: str | None = None


class ArchiveBatchResult(BaseModel):
    created: int
    already: int
    skipped: int
    items: list[ArchiveBatchItem]


class ArchiveVerifyRequest(BaseModel):
    # Boş bırakılırsa var olan tüm arşivler doğrulanır.
    claim_ids: list[str] | None = None


class ArchiveVerifyItem(BaseModel):
    evidence_id: str
    claim_id: str
    status: str | None = None
    status_label: str | None = None
    match: float | None = None
    note: str | None = None
    scored: bool = False
    # Doğrulamanın claim'e ETKİSİ: skor ve durum değişti mi. Fazın sınavı tam olarak bu.
    confidence_before: float | None = None
    confidence_after: float | None = None
    state_before: str | None = None
    state_after: str | None = None


class ArchiveVerifyResult(BaseModel):
    checked: int
    verified: int
    changed: int
    unreachable: int
    state_changes: int
    items: list[ArchiveVerifyItem]


class ReparseRequest(BaseModel):
    """Faz 25 — saklanmış `mode=web` metnini yeni ayrıştırıcıyla onarma isteği."""

    # Boş bırakılırsa aday havuzu kendisi belirlenir: URL'i olan ve DOCINT'ten gelmeyen
    # gözlemler. Belirli id'ler verilirse yalnızca onlara bakılır.
    observation_ids: list[str] | None = None
    # Varsayılan KURU: bu uç var olan veriyi ÜZERİNE yazıyor. Ne yazılacağını görmeden
    # yazmak, düzeltmeye çalıştığımız sessiz bozulmanın aynısını üretirdi.
    dry_run: bool = True


class ReparseItem(BaseModel):
    observation_id: str
    source_url: str | None = None
    action: str  # "onarildi" | "onarilabilir" | "atlandi"
    reason: str | None = None
    old_length: int
    new_length: int | None = None
    containment: float | None = None
    new_headline: str | None = None
    claim_ids: list[str] = []


class ReparseResult(BaseModel):
    dry_run: bool
    considered: int
    repaired: int
    repairable: int
    items: list[ReparseItem]


SCAN_MODES = ("rss", "web", "telegram")

# Varsayılan aralık: 3 saat. Faz 11'in gerçek kullanım deseni (günde bir-iki oturum, izlenen
# feed'ler günde birkaç kez yayın yapıyor) için "birkaç saat içinde haberim olsun" ihtiyacını
# karşılıyor; daha sık taramak yayıncıya karşı da kabalık olurdu. Alt sınır 15 dakika aynı
# nedenle konuldu — bu bir haber okuyucusu değil, bir istihbarat defteri.
DEFAULT_SCAN_INTERVAL_MINUTES = 180
MIN_SCAN_INTERVAL_MINUTES = 15


class ScanScheduleCreate(BaseModel):
    """Faz 12 — bir kaynağın periyodik olarak taranması.

    `source_id` zorunlu: toplanan Observation'ın kime ait olduğu ve Inbox bildiriminin hangi
    hedef üzerinden gideceği (Monitor target_type='Source') buradan gelir. Kaynağı olmayan
    bir otomatik tarama, sonradan promote edilemeyen içerik biriktirirdi."""

    source_id: str
    url: str | None = Field(
        None, description="Taranacak adres. Verilmezse Source.url kullanılır — feed adresi çoğu zaman ondan farklıdır (ör. /feed/)"
    )
    mode: str = Field("rss", examples=list(SCAN_MODES))
    interval_minutes: int = Field(DEFAULT_SCAN_INTERVAL_MINUTES, ge=MIN_SCAN_INTERVAL_MINUTES, le=10080)
    # Faz 11 (F2)'nin dersi zamanlanmış taramada daha da kritik: elle tarama bir kez patlar,
    # zamanlanmış tarama her koşuda patlar. Varsayılanlar bilerek dar.
    item_limit: int = Field(20, ge=1, le=500)
    since_days: int | None = Field(7, ge=1, le=MAX_SINCE_DAYS)
    label: str | None = None
    watch: bool = Field(
        True,
        description="Kaynak için otomatik bir Monitor aç — bu olmadan tarama sessizce çalışır, Inbox'a hiçbir şey düşmez",
    )


class ScanScheduleUpdate(BaseModel):
    interval_minutes: int | None = Field(None, ge=MIN_SCAN_INTERVAL_MINUTES, le=10080)
    item_limit: int | None = Field(None, ge=1, le=500)
    since_days: int | None = Field(None, ge=1, le=MAX_SINCE_DAYS)
    label: str | None = None
    active: bool | None = None


class ScanSchedule(BaseModel):
    id: str
    source_id: str
    source_name: str | None = None
    url: str
    mode: str
    interval_minutes: int
    item_limit: int
    since_days: int | None
    label: str | None
    active: bool
    # Çalışma durumu — "bu tarama gerçekten çalışıyor mu" sorusunun arayüzden cevabı.
    last_run_at: datetime | None
    last_status: str | None
    last_error: str | None
    last_new_count: int | None
    consecutive_failures: int
    next_run_at: datetime | None
    monitored: bool
    created_at: datetime


class InvolvedInLink(BaseModel):
    role: str = Field(..., examples=["katılımcı", "fail", "mağdur", "tanık"])


class EventUpdate(BaseModel):
    """Faz 18: bir olayın başlığı/türü/zamanı sonradan düzeltilebilmeli.

    History Is Immutable ile çelişmez: bir Event kaynağın iddiası değil, bizim
    SINIFLANDIRMAMIZ — olayın ne zaman olduğu genellikle ilk claim'den sonra netleşir.
    Verilmeyen alanlar dokunulmadan kalır (`None` "temizle" demek DEĞİL, bu yüzden
    `occurred_at`/`location` temizlemek için boş string / sentinel değil, ayrı bir çağrı
    gerekmez — açıkça `null` gönderilen alan da atlanır)."""

    title: str | None = None
    event_type: str | None = None
    occurred_at: UtcDatetime | None = None
    location: str | None = None


class EventCandidateClaim(BaseModel):
    id: str
    text: str
    knowledge_state: str
    confidence: float
    created_at: datetime
    source_id: str | None = None
    source_name: str | None = None
    about_entity_id: str | None = None
    about_entity_name: str | None = None
    superseded_by_claim_id: str | None = None


class EventCandidate(BaseModel):
    """Faz 18 — `CORROBORATES` bağlarının bir bağlantılı bileşeni: "bunlar aynı olay" önerisi.

    `source_count` ile `independent_source_count` bilerek AYRI: Q6/Faz 6'dan beri "iki farklı
    site" ile "iki bağımsız kaynak" aynı şey değil. Kartta yalnızca ham sayı gösterilseydi,
    aynı ajanstan türeyen 4 site "4 kaynak doğruladı" diye okunurdu — Faz 17'nin engellemek
    için kurulduğu hatanın birebir aynısı."""

    claims: list[EventCandidateClaim]
    claim_count: int
    source_count: int
    independent_source_count: int
    entities: list[dict]
    first_seen: datetime | None = None
    last_seen: datetime | None = None


class EventFromCluster(EventCreate):
    """Bir olay adayını gerçek bir Event'e çevirir — başlığı insan verir (Design Principle #7).

    `claim_ids` kümenin tamamı olmak zorunda değil: kullanıcı bir claim'i dışarıda bırakarak
    kümeyi bölebilir. `carry_entities` varsayılan olarak açık, çünkü bir claim aynı anda hem
    entity hem event hakkında OLAMAZ (ABOUT_ENTITY siliniyor) — o bağ INVOLVED_IN olarak
    olaya taşınmazsa, olay kurmak entity'yi fakirleştirirdi."""

    claim_ids: list[str]
    carry_entities: bool = True
    entity_role: str = "ilgili"


class EventFromClusterResult(BaseModel):
    event: Event
    linked_claims: int
    linked_entities: list[dict] = Field(default_factory=list)
    linked_sources: int = 0


# Faz 12: "Source" eklendi — zamanlanmış tarama yeni içerik bulduğunda Inbox'a düşen
# bildirimin hedefi bir kaynaktır ("Krebs on Security'de 3 yeni içerik"), tek tek gözlemler
# değil. Gözlem başına bildirim, günde bir düzine öğe yayınlayan bir feed'de Inbox'ı
# kullanılamaz hale getirirdi ("more signal, less noise", madde 25).
MONITOR_TARGET_TYPES = ("Entity", "Event", "Investigation", "Source", "Selector")


class MonitorCreate(BaseModel):
    target_type: str = Field(..., examples=list(MONITOR_TARGET_TYPES))
    target_id: str
    label: str | None = None


class Monitor(MonitorCreate):
    id: str
    active: bool
    created_at: datetime


INBOX_ITEM_TYPES = (
    "NEW_EVENT", "NEW_RELATIONSHIP", "SIGNIFICANT_CHANGE",
    "INVESTIGATION_UPDATE", "CONTRADICTION", "CONFIDENCE_CHANGED",
    # Faz 12 — zamanlanmış tarama: bir tarama koşusunda yeni içerik bulundu / tarama
    # üst üste başarısız oldu. İkincisi olmadan ölü bir feed sessizce ölü kalırdı.
    "NEW_OBSERVATION", "SCAN_FAILED",
)
PRIORITY_LEVELS = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO")
# Q13: sabit sıralama — "sadece HIGH+ göster" gibi bir eşik bu sıradaki index'e göre uygulanır.
PRIORITY_ORDER = {p: i for i, p in enumerate(PRIORITY_LEVELS)}

# Q14: davranış geri beslemesi loglanır ama v1'de prioritization'ı otomatik etkilemez.
INBOX_ITEM_STATUSES = ("NEW", "IGNORED", "CONFIRMED", "REJECTED", "INVESTIGATING", "FOLLOWED")


class InboxItem(BaseModel):
    id: str
    item_type: str
    priority: str
    title: str
    detail: dict
    target_type: str
    target_id: str
    monitor_id: str | None
    status: str
    created_at: datetime
    actioned_at: datetime | None


class InboxStatusUpdate(BaseModel):
    status: str = Field(..., examples=list(INBOX_ITEM_STATUSES[1:]))


class InboxSettings(BaseModel):
    min_priority: str = Field("INFO", examples=list(PRIORITY_LEVELS))
