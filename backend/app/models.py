from datetime import datetime

from pydantic import BaseModel, Field


class EntityCreate(BaseModel):
    entity_type: str = Field(..., examples=["Person", "Organization", "Company", "Location"])
    name: str
    aliases: list[str] = Field(default_factory=list)


class Entity(EntityCreate):
    id: str
    created_at: datetime


class EntityRelationCreate(BaseModel):
    to_entity_id: str
    relation_type: str = Field(..., examples=["çalışıyor", "sahibi", "ortak", "aile"])
    confidence: float = Field(0.5, ge=0.0, le=1.0)


SAME_AS_STATUSES = ("PENDING", "CONFIRMED", "REJECTED")


class SameAsSuggestRequest(BaseModel):
    to_entity_id: str


class EventCreate(BaseModel):
    title: str
    event_type: str = Field(..., examples=["saldırı", "seçim", "açıklama", "satın alma"])
    occurred_at: datetime | None = None
    location: str | None = None


class Event(EventCreate):
    id: str
    knowledge_state: str
    confidence: float
    created_at: datetime


class SourceCreate(BaseModel):
    name: str
    source_type: str = Field(..., examples=["haber sitesi", "resmi açıklama", "sosyal medya"])
    url: str | None = None
    reliability: float = Field(0.5, ge=0.0, le=1.0)


class Source(SourceCreate):
    id: str
    created_at: datetime


class EvidenceCreate(BaseModel):
    evidence_type: str = Field(..., examples=["fotoğraf", "video", "belge", "uydu görüntüsü"])
    file_path: str | None = None
    content_hash: str | None = None
    collected_at: datetime | None = None


class Evidence(EvidenceCreate):
    id: str
    created_at: datetime


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
    text: str
    source_id: str
    # Faz 11 (dogfooding F12): iddianın GEÇERLİLİK başlangıcı — kayıt anı değil. Verilmezse
    # "şimdi"ye düşer. Arşivden toplanan eski bir haber bugün kaydedilse bile temporal
    # sıralama (supersede) yayın tarihine göre yapılmalı, toplama anına göre değil.
    valid_from: datetime | None = None
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
    raw_content: str
    observed_at: datetime | None = None
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
    title: str
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
    text: str = Field(..., examples=["H1: Company X is directly controlled by Organization Y."])


class Hypothesis(HypothesisCreate):
    id: str
    status: str
    created_at: datetime


class HypothesisEvidenceLink(BaseModel):
    evidence_id: str
    stance: str = Field(..., examples=["SUPPORTS", "WEAKENS", "REFUTES"])


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
    mode: str = Field(..., examples=["rss", "web"])
    # Faz 11 (dogfooding F2): bazı feed'ler tüm arşivi yayınlıyor (ör. openai.com/news:
    # 1164 item). Limitsiz tarama sistemi tek hamlede kullanılamaz hale getiriyordu.
    limit: int = Field(default=50, ge=1, le=500)
    # Opsiyonel zaman penceresi: sadece son N günde yayınlanmış item'ları al.
    since_days: int | None = Field(default=None, ge=1)


SCAN_MODES = ("rss", "web")

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
    since_days: int | None = Field(7, ge=1)
    label: str | None = None
    watch: bool = Field(
        True,
        description="Kaynak için otomatik bir Monitor aç — bu olmadan tarama sessizce çalışır, Inbox'a hiçbir şey düşmez",
    )


class ScanScheduleUpdate(BaseModel):
    interval_minutes: int | None = Field(None, ge=MIN_SCAN_INTERVAL_MINUTES, le=10080)
    item_limit: int | None = Field(None, ge=1, le=500)
    since_days: int | None = Field(None, ge=1)
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


# Faz 12: "Source" eklendi — zamanlanmış tarama yeni içerik bulduğunda Inbox'a düşen
# bildirimin hedefi bir kaynaktır ("Krebs on Security'de 3 yeni içerik"), tek tek gözlemler
# değil. Gözlem başına bildirim, günde bir düzine öğe yayınlayan bir feed'de Inbox'ı
# kullanılamaz hale getirirdi ("more signal, less noise", madde 25).
MONITOR_TARGET_TYPES = ("Entity", "Event", "Investigation", "Source")


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
