// Backend'in Pydantic modelleriyle (backend/app/models.py) birebir eşleşir.

export type KnowledgeState =
  | "UNKNOWN"
  | "OBSERVED"
  | "REPORTED"
  | "SUPPORTED"
  | "CORROBORATED"
  | "HIGH_CONFIDENCE"
  | "CONTRADICTED";

export type Priority = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "INFO";

export type InboxStatus = "NEW" | "IGNORED" | "CONFIRMED" | "REJECTED" | "INVESTIGATING" | "FOLLOWED";

export type InvestigationStatus = "OPEN" | "ACTIVE" | "PAUSED" | "RESOLVED" | "CLOSED" | "ARCHIVED";

// Q15 — SOURCE FACT/AI ANALYSIS/SYSTEM INFERENCE/USER INTERPRETATION henüz backend'de
// alan olarak tutulmuyor (bkz. frontend/README notu); UI bunu içerik kaynağına göre türetir.
export type ProvenanceLabel = "SOURCE_FACT" | "AI_ANALYSIS" | "SYSTEM_INFERENCE" | "USER_INTERPRETATION";

export interface Entity {
  id: string;
  entity_type: string;
  name: string;
  aliases: string[];
  created_at: string;
}

export interface EventItem {
  id: string;
  title: string;
  event_type: string;
  occurred_at: string | null;
  location: string | null;
  knowledge_state: KnowledgeState;
  confidence: number;
  created_at: string;
}

export interface Source {
  id: string;
  name: string;
  source_type: string;
  url: string | null;
  reliability: number;
  created_at: string;
}

export interface Claim {
  id: string;
  text: string;
  source_id: string;
  about_entity_id: string | null;
  about_event_id: string | null;
  knowledge_state: KnowledgeState;
  confidence: number;
  valid_from: string;
  valid_to: string | null;
  // Faz 11 (F34): SUPERSEDES yazılıyor ama hiç okunmuyordu — eskimiş claim güncel olanla
  // aynı görünüyordu. Gizlemiyoruz (History Is Immutable), işaretliyoruz.
  superseded_by_claim_id: string | null;
  supersedes_claim_id: string | null;
  created_at: string;
  updated_at: string;
}

/** Faz 15.1 (DOCINT) — bir belgenin çıkarma durumu.
 *
 * `NO_TEXT_LAYER` neden `DONE`den ayrı: taranmış (görüntü) bir PDF hata VERMEDEN 0 karakter
 * döndürüyor. Tek bir "metin var mı" kontrolü böyle bir belgeyi "işlendi, metni boş" diye
 * gösterirdi — belge sisteme girmiş görünür, içeriği hiçbir yere ulaşmaz. */
export type ExtractionStatus =
  | "PENDING"
  | "RUNNING"
  | "DONE"
  | "NO_TEXT_LAYER"
  | "ENCRYPTED"
  | "CORRUPT"
  | "UNSUPPORTED"
  | "FAILED";

/** Faz 15.2 (Q22) — toplanan içerikte bulunan talimat-görünümlü bir ifade.
 *
 * Bu bir güvenlik sınırı değil, bir HABER VERME mekanizması: asıl koruma, bu metnin hiçbir
 * katmanda komut olarak yürütülmemesi. `where` ifadenin nereden geldiğini söyler ("metin",
 * "metadata:Subject", "gözlem metni") — Faz 15 spike'ı aynı ifadenin hem belge metninde hem
 * metadata alanında taşınabildiğini doğruladı. */
export interface InjectionHit {
  where: string;
  match: string;
  snippet: string;
}

/** Faz 15.3 — belge metadata'sının tek bir alanı.
 *
 * **Q22: `value` güvenilmeyen veridir** — belgeyi kim ürettiyse o yazmıştır. Gösterilir,
 * asla yorumlanmaz. `linkable` yalnızca kişi/kuruma işaret edebilecek alanlarda true
 * (Creator/Producer yazılım adı taşır; onları bağlamak grafı yazılım adlarıyla kirletirdi).
 * `note` alanın kendi başına söylemediği çıkarım — ör. tarih damgasındaki saat dilimi. */
export interface FingerprintField {
  field: string;
  value: string;
  linkable: boolean;
  note: string | null;
}

export interface FingerprintGroup {
  key: string;
  label: string;
  fields: FingerprintField[];
}

export interface FingerprintLink {
  entity_id: string;
  entity_name: string;
  entity_type: string;
  field: string;
  value: string;
}

/** Belgenin üretildiği ortamın izi — içeriği değil: kim yazdı, hangi araçla, ne zaman,
 * hangi kurumun sisteminden geçti. */
export interface EvidenceFingerprint {
  evidence_id: string;
  groups: FingerprintGroup[];
  links: FingerprintLink[];
  /** Yalnızca METADATA kaynaklı uyarılar; belge metnindekiler EvidenceExtraction'da. */
  injection_hits: InjectionHit[];
}

export interface Evidence {
  id: string;
  evidence_type: string;
  file_path: string | null;
  content_hash: string | null;
  collected_at: string | null;
  created_at: string;
  // Faz 15.1 — hepsi opsiyonel: kanıt PDF olmak zorunda değil ve bu fazdan önce yüklenmiş
  // kayıtlarda NULL. Tam metin bilerek burada yok (tek belge 1,65M karakter olabiliyor).
  extraction_status: ExtractionStatus | null;
  extraction_status_label: string | null;
  page_count: number | null;
  pages_done: number | null;
  extraction_error: string | null;
  extracted_at: string | null;
  /** Faz 15.4 — metnin kaynağı: "extracted" (belgenin kendi metin katmanı) ya da "ocr"
   * (görüntüden TAHMİN). İkisi aynı güvenilirlikte değildir ve bu ayrım arayüzde görünür
   * kalmalı — fazın bitti kriteri bunu şart koşuyor. */
  text_source: "extracted" | "ocr" | null;
  ocr_confidence: number | null;
  ocr_lang: string | null;
}

/** Faz 15.1 — `GET /evidence/{id}/extraction` yanıtı.
 *
 * **Q22:** `metadata` ve `text_preview` GÜVENİLMEYEN VERİDİR. Belge metni ve metadata'sı
 * açık kaynaktan gelir; Faz 15 spike'ı ikisinin de talimat-görünümlü ifade taşıyabildiğini
 * doğruladı. Bu alanlar gösterilir, asla komut olarak yorumlanmaz. */
export interface EvidenceExtraction {
  evidence_id: string;
  status: ExtractionStatus | null;
  status_label: string | null;
  page_count: number | null;
  pages_done: number | null;
  error: string | null;
  extracted_at: string | null;
  metadata: Record<string, string>;
  text_chars: number;
  text_preview: string;
  /** Boş liste "temiz" demek değil, "bilinen desenlerden hiçbiri eşleşmedi" demek. */
  injection_hits: InjectionHit[];
  text_source: "extracted" | "ocr" | null;
  ocr_confidence: number | null;
  ocr_lang: string | null;
}

export interface Investigation {
  id: string;
  title: string;
  research_question: string;
  status: InvestigationStatus;
  // Faz 13 (madde 30): zincirin son iki adımı. Bunlar olmadan bir investigation, cevabı
  // hiçbir yere yazılmadan kapatılabiliyordu — soru vardı, karşılığı yoktu.
  analysis: string | null;
  conclusion: string | null;
  concluded_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface Hypothesis {
  id: string;
  text: string;
  status: "PROPOSED" | "SUPPORTED" | "WEAKENED" | "REFUTED" | "UNRESOLVED";
  created_at: string;
}

export interface HypothesisEvidenceLink {
  evidence_id: string;
  evidence_type: string;
  file_path: string | null;
  stance: "SUPPORTS" | "WEAKENS" | "REFUTES";
}

export interface Observation {
  id: string;
  raw_content: string;
  observed_at: string | null;
  source_url: string | null;
  promoted: boolean;
  created_at: string;
  // Faz 11 (F32): `promoted` sadece eşiği GEÇEN durumu işaretler. Eşiği geçmeyen bir promote
  // de claim üretir; bu alan olmadan "hiç işlenmemiş" ile "işlendi, eşiği geçmedi" ayırt
  // edilemiyordu.
  produced_claim_id: string | null;
  /** Faz 16 — "değerlendirildi, bilgiye dönüştürülmedi". `promoted: false` tek başına iki
   * ayrı hâli anlatmak zorundaydı ("henüz bakılmadı" ve "bakıldı, yükseltilmedi"); bu ayrım
   * olmadan elenen gözlem ertesi gün yine kuyruğun içinde duruyordu. Kayıt SİLİNMEZ. */
  dismissed: boolean;
  dismissed_at: string | null;
  dismiss_reason: string | null;
  /** Faz 15.2 — gözlem bir belgeden geldiyse hangi belgenin hangi sayfalarından geldiği.
   * Collector'dan gelen gözlemlerde null (onların provenance'ı `source_url`). Belge tabanlı
   * gözlemlerin URL'i YOKTUR; `source_url`'e uydurma bir değer yazmak yerine ayrı alan. */
  from_evidence: {
    evidence_id: string;
    page_from: number;
    page_to: number;
    file_name: string | null;
  } | null;
  /** Faz 15.2 (Q22) — bu gözlemin KENDİ metnindeki talimat-görünümlü ifadeler. Uyarı metinle
   * birlikte seyahat ediyor: promote kararı burada veriliyor, uyarı yalnızca kaynak belgede
   * dursaydı kullanıcı bir iddiayı grafa yükseltirken onu görmeyebilirdi. */
  injection_hits: InjectionHit[];
  /** Faz 15.4 — gözlemin metni OCR'dan geldiyse işaret onunla birlikte seyahat eder:
   * promote kararı bu gözlem üzerinde veriliyor. */
  text_source: "extracted" | "ocr" | null;
}

export interface Monitor {
  id: string;
  // Faz 12: "Source" — zamanlanmış tarama bildirimleri kaynak üzerinden gider.
  target_type: "Entity" | "Event" | "Investigation" | "Source" | "Selector";
  target_id: string;
  label: string | null;
  active: boolean;
  created_at: string;
}

export interface InboxItem {
  id: string;
  item_type: string;
  priority: Priority;
  title: string;
  detail: Record<string, unknown>;
  target_type: string;
  target_id: string;
  monitor_id: string | null;
  status: InboxStatus;
  created_at: string;
  actioned_at: string | null;
}

/** Faz 12 — bir kaynağın periyodik taranması. `next_run_at`/`last_*` alanları "bu tarama
 * gerçekten çalışıyor mu" sorusunun arayüzdeki cevabı; `monitored` false ise tarama çalışır
 * ama Inbox'a hiçbir şey düşmez (sessiz tuzak — UI'da uyarı gösteriliyor). */
export interface ScanSchedule {
  id: string;
  source_id: string;
  source_name: string | null;
  url: string;
  mode: "rss" | "web" | "telegram";
  interval_minutes: number;
  item_limit: number;
  since_days: number | null;
  label: string | null;
  active: boolean;
  last_run_at: string | null;
  last_status: "OK" | "ERROR" | null;
  last_error: string | null;
  last_new_count: number | null;
  consecutive_failures: number;
  next_run_at: string | null;
  monitored: boolean;
  created_at: string;
}

export interface ScanRunResult {
  schedule_id: string;
  status: "OK" | "ERROR";
  error?: string;
  observations_created: number;
  observation_ids?: string[];
  duplicates_skipped?: number;
  items_available?: number;
  consecutive_failures?: number;
  notified: { id: string; priority: string } | null;
}

/** Faz 13 — Evidence Vault satırı.
 *
 * `has_file` saklanan değil hesaplanan bir alan: `file_path` dolu olsa bile dosya yerinde
 * olmayabilir (elle girilmiş yol, taşınmış dosya). İndirilemeyen bir kanıtı indirilebilir
 * göstermemek için gerekli.
 *
 * `linked_claims` Faz 13'te açılan bir boşluk: Evidence→Claim SUPPORTS/CONTRADICTS kenarları
 * Faz 10'dan beri yazılıyor ve confidence hesabında sayılıyordu, ama hiçbir uç listelemiyordu. */
/** Faz 13 (madde 30) — Investigation Workspace'in tam zinciri.
 *
 * Ara adımlar (sources/observations/claims/evidence) SAKLANMIYOR, graf'tan TÜRETİLİYOR:
 * kapsamdaki entity/event'lerden ve finding'lerden geriye doğru yürünüyor. Yeni ilişki
 * tabloları eklemek, kullanıcıdan zaten grafta duran bağları elle bir kez daha kurmasını
 * istemek olurdu — ve elle kurulan her bağ, kurulmayı unutulabilen bir bağdır. */
export interface InvestigationWorkspace {
  investigation: Investigation;
  scope: {
    entities: { id: string; name: string; entity_type: string }[];
    events: { id: string; title: string; event_type: string }[];
  };
  sources: { id: string; name: string; source_type: string; reliability: number }[];
  observations: {
    id: string;
    headline: string;
    source_url: string | null;
    observed_at: string | null;
    promoted: boolean;
  }[];
  claims: {
    id: string;
    headline: string;
    knowledge_state: KnowledgeState;
    confidence: number;
    valid_from: string;
    valid_to: string | null;
    is_finding: boolean;
    superseded: boolean;
  }[];
  evidence: {
    id: string;
    evidence_type: string;
    file_path: string | null;
    content_hash: string | null;
    stance: "SUPPORTS" | "CONTRADICTS";
  }[];
  hypotheses: Hypothesis[];
  findings: string[];
  steps: Record<WorkflowStep, boolean>;
}

export type WorkflowStep =
  | "research_question"
  | "scope"
  | "sources"
  | "observations"
  | "claims"
  | "evidence"
  | "hypotheses"
  | "analysis"
  | "findings"
  | "conclusion";

export interface EvidenceVaultItem extends Evidence {
  has_file: boolean;
  linked_claims: {
    claim_id: string;
    headline: string;
    knowledge_state: KnowledgeState;
    confidence: number;
    source_id: string | null;
    source_name: string | null;
    stance: "SUPPORTS" | "CONTRADICTS";
  }[];
}

/** Faz 13 — lineage zincirindeki bir düğüm. `depth` kaç hop uzakta olduğunu söyler;
 * onsuz "zincir" gösterilemez, yalnızca sırasız bir küme gösterilebilir. */
export interface LineageNode {
  id: string;
  name: string;
  url: string | null;
  depth: number;
}

/** Faz 13 — bir kaynağın attığı claim. `superseded_by_claim_id` bilerek burada: F34'ün
 * dersi, yerini almış bir claim'in güncel olanla birebir aynı görünmemesi gerektiğiydi. */
export interface SourceClaim {
  id: string;
  text: string;
  knowledge_state: KnowledgeState;
  confidence: number;
  valid_from: string;
  valid_to: string | null;
  created_at: string;
  about_entity_id: string | null;
  about_entity_name: string | null;
  about_event_id: string | null;
  about_event_title: string | null;
  superseded_by_claim_id: string | null;
}

export interface WhyMattersReason {
  code: string;
  text: string;
  detail: Record<string, unknown>;
}

export interface EntityRecall {
  // Faz 11 (F31): recall artık onaylanmış SAME_AS grubunu da kapsıyor. `via_entity_name`,
  // satırın başka bir (aynı olduğu onaylanmış) kayıttan geldiğini söyler; kendi kaydıysa null.
  related_investigations: (Pick<Investigation, "id" | "title" | "status" | "created_at"> & {
    via_entity_name: string | null;
  })[];
  related_claims: (Pick<Claim, "id" | "text" | "knowledge_state" | "confidence" | "created_at"> & {
    via_entity_name: string | null;
    superseded_by_claim_id: string | null;
    source_id: string | null;
    source_name: string | null;
    source_url: string | null;
  })[];
  // Faz 18: `occurred_at` + durum alanları eklendi — timeline olayları KAYIT tarihine göre
  // diziyordu, oysa bir olayın çizgideki yeri ne zaman OLDUĞUdur.
  // Faz 21: adı geçen ama ÖZNESİ olmadığı claim'ler. `related_claims` ile karıştırılmamalı —
  // değme, iddianın bu entity HAKKINDA olduğu anlamına gelmez.
  mentioned_in: (MentionedInClaim & { via_entity_name: string | null })[];
  related_events: (Pick<
    EventItem,
    "id" | "title" | "event_type" | "occurred_at" | "knowledge_state" | "confidence" | "created_at"
  > & {
    via_entity_name: string | null;
  })[];
  same_as: Pick<Entity, "id" | "name" | "entity_type">[];
}

export interface EventRecall {
  related_investigations: Pick<Investigation, "id" | "title" | "status" | "created_at">[];
  related_claims: Pick<Claim, "id" | "text" | "knowledge_state" | "confidence" | "created_at">[];
  related_entities: Pick<Entity, "id" | "name" | "entity_type">[];
  reported_by: Pick<Source, "id" | "name" | "source_type">[];
}

export interface EntityRelation {
  entity_id: string;
  name: string;
  relation_type: string;
  confidence: number;
  status: string;
  valid_from: string;
  direction: "OUTGOING" | "INCOMING";
}

export interface SameAsCandidate {
  entity_id: string;
  name: string;
  entity_type: string;
  score: number;
}

export interface SameAsPending {
  entity_a_id: string;
  entity_a_name: string;
  entity_a_type: string;
  entity_b_id: string;
  entity_b_name: string;
  entity_b_type: string;
  confidence: number;
  created_at: string;
}

/** Faz 16 — bir gözlemin kuyrukta neden bu sırada olduğunun tek gerekçesi. Skor tek bir
 * sayı olsaydı kuyruk kara kutu olurdu: 180 kaydı toplu elerken kullanıcının neye güvendiğini
 * bilmesi gerekiyor. `weight: 0` olan gerekçeler (injection uyarısı, OCR) sıralamayı
 * etkilemez, sadece dikkat çeker. */
export interface SignalReason {
  code: string;
  text: string;
  weight: number;
}

export interface QueueItem extends Observation {
  signal_score: number;
  signal_reasons: SignalReason[];
  matched_entities: { id: string; name: string; matched_on: string }[];
  /** Hızlı promote'un "önerilir, kullanıcı onaylar" tarafı (Design Principle #7). */
  suggested_source_id: string | null;
  suggested_source_name: string | null;
  suggested_entity_id: string | null;
  host: string | null;
  age_days: number;
}

export interface QueueHostBucket {
  host: string;
  count: number;
  high_signal: number;
}

export interface QueueStats {
  pending: number;
  dismissed: number;
  evaluated: number;
  total: number;
  high_signal: number;
  noise: number;
  oldest_pending_at: string | null;
  oldest_pending_age_days: number | null;
  hosts: QueueHostBucket[];
}

export interface ObservationQueue {
  stats: QueueStats;
  items: QueueItem[];
  /** Filtreden geçen toplam — `items` sayfalanmış olabilir. */
  matched: number;
  high_signal_threshold: number;
}

export interface ObservationDismissResult {
  dismissed: number;
  /** Zaten claim üretmiş ya da bulunamamış id'ler — sessizce yutulmuyor. */
  skipped: string[];
}

export interface ObservationPromoteBatchItem {
  observation_id: string;
  /** PROMOTED (eşiği geçti) · BELOW_THRESHOLD (claim üretildi, eşiğin altında) · SKIPPED.
   * Üçü ayrı, çünkü ikincisi bir hata değil — Q1'in katmanlı hafıza modelinin normal sonucu. */
  status: "PROMOTED" | "BELOW_THRESHOLD" | "SKIPPED";
  headline: string;
  claim_id: string | null;
  confidence: number | null;
  message: string | null;
}

export interface ObservationPromoteBatchResult {
  promoted: number;
  below_threshold: number;
  skipped: number;
  items: ObservationPromoteBatchItem[];
}

/** Faz 17 — aday listesinde bir claim'in gösterilmesi için gereken minimum. */
export interface CandidateClaim {
  id: string;
  text: string;
  source_id: string;
  source_name: string;
  confidence: number;
  knowledge_state: KnowledgeState;
  valid_from: string;
}

/** Faz 17'nin en önemli ayrımı: aynı ölçüm üç farklı sonuca çıkabiliyor ve yalnızca ilki
 * bağlanabilir. Diğerlerini "iki kaynak" sanıp bağlamak confidence'ı SAHTE yükseltirdi —
 * bu fazın önlemesi gereken asıl hata bu. */
export type CandidateKind =
  | "CORROBORATION"
  | "DERIVED_SUSPECT"
  | "SHARED_ROOT"
  | "SAME_SOURCE_DUPLICATE";

export interface CorroborationCandidate {
  claim_a: CandidateClaim;
  claim_b: CandidateClaim;
  kind: CandidateKind;
  rare_overlap: number;
  text_similarity: number;
  days_apart: number;
  shared_terms: string[];
  reasons: string[];
  /** Bağlanırsa confidence nereye gider — bu fazın var olma sebebi tam olarak bu hareket. */
  projected_a: number | null;
  projected_b: number | null;
}

export interface ClaimLinkResult {
  claim_a_id: string;
  claim_b_id: string;
  link: "CORROBORATES" | "CONTRADICTS";
  status: "LINKED" | "SKIPPED";
  message: string | null;
  confidence_before: Record<string, number>;
  confidence_after: Record<string, number>;
  state_after: Record<string, KnowledgeState>;
}

export interface ClaimLinkBatchResult {
  linked: number;
  skipped: number;
  results: ClaimLinkResult[];
}

export interface ObservationPromoteResult {
  claim: Claim;
  recall: (Partial<EntityRecall & EventRecall> & { about: "entity" | "event"; id: string }) | null;
  why_matters: WhyMattersReason[];
}

export interface CollectorFetchResult {
  final_url: string;
  content_type: string;
  items_available: number;
  items_considered: number;
  observations_created: number;
  duplicates_skipped: number;
  observation_ids: string[];
}


/** Faz 18 — bir olay adayının içindeki claim. `about_entity_*`, olayı kurduğunda o claim'in
 *  entity bağının nereye taşınacağını (INVOLVED_IN) önceden gösterir. */
export interface EventCandidateClaim {
  id: string;
  text: string;
  knowledge_state: KnowledgeState;
  confidence: number;
  created_at: string;
  source_id: string | null;
  source_name: string | null;
  about_entity_id: string | null;
  about_entity_name: string | null;
  superseded_by_claim_id: string | null;
}

/** `source_count` ile `independent_source_count` bilerek ayrı: "4 site bildirdi" ile
 *  "4 bağımsız kaynak doğruladı" aynı şey değil (Q6/Faz 6). */
export interface EventCandidate {
  claims: EventCandidateClaim[];
  claim_count: number;
  source_count: number;
  independent_source_count: number;
  entities: { id: string; name: string }[];
  first_seen: string | null;
  last_seen: string | null;
}

export interface EventFromClusterResult {
  event: EventItem;
  linked_claims: number;
  linked_entities: { id: string; name: string; role: string }[];
  linked_sources: number;
}

/** Faz 18 yan onarımı: confidence kırılımı artık skorun KAYNAĞINI da taşıyor. */
export interface ClaimExplain {
  claim_id: string;
  source_quality: number;
  independence: number;
  evidence: number;
  corroboration: number;
  confidence: number;
  knowledge_state: KnowledgeState;
  weights: Record<"source_quality" | "independence" | "evidence" | "corroboration", number>;
  corroborated_by: {
    claim_id: string;
    text: string;
    knowledge_state: KnowledgeState;
    confidence: number;
    source_id: string;
    source_name: string;
    independent_root_id: string;
    // false ise: bu kaynak, zaten sayılmış bir kaynakla aynı DERIVED_FROM kökünde —
    // doğruluyor ama bağımsızlık skoruna İKİNCİ kez katkı yapmıyor.
    counts_for_independence: boolean;
  }[];
  /** Faz 26 — kanıt alt-skorunun kaynağı. Arşiv kayıtları `archive_status` ile ayrışıyor:
   *  bir arşiv skora ancak DOGRULANDI durumundayken girer. */
  evidence_from: {
    evidence_id: string;
    evidence_type: string;
    archive_status: ArchiveStatus | null;
    archive_url: string | null;
    content_hash: string | null;
  }[];
}


/** Faz 19 — "bu iki entity ilişkili olabilir" önerisi.
 *
 * `co_mention_count` (claim metninde birlikte anılma) ile `shared_event_count` (aynı olaya
 * karışma) bilerek AYRI alanlar: ilki zayıf kanıt — aynı haberde iki ad geçebilir; ikincisi
 * güçlü — kullanıcının kendi kurduğu bir bağ. Tek skora karıştırılsalardı fark kaybolurdu.
 *
 * İlişkinin TÜRÜ burada YOK ve olmayacak: sistem tahmin etmez, kullanıcı yazar. */
export interface RelationCandidate {
  entity_id: string;
  name: string;
  entity_type: string;
  co_mention_count: number;
  shared_event_count: number;
  shared_events: { id: string; title: string }[];
  evidence: { claim_id: string; excerpt: string; matched_on: string }[];
}


/** Faz 20 — claim metninden deterministik olarak çıkarılmış entity adayı.
 *
 * `key` normalize edilmiş addır ve kararın kalıcı anahtarı: adaylar saklanmaz, her istekte
 * yeniden çıkarılır; saklanan tek şey kullanıcının verdiği karardır (elenen bir aday tekrar
 * önerilmez).
 *
 * `claim_count` ile `source_count` ayrı: tek bir haberde geçen özel isim ile beş farklı
 * kaynakta geçen kurum aynı ağırlıkta olmamalı. */
export interface ExtractedEntityCandidate {
  key: string;
  name: string;
  claim_count: number;
  source_count: number;
  source_names: string[];
  evidence: { claim_id: string; excerpt: string }[];
  status: "PENDING" | "DISMISSED" | "PROMOTED";
  promoted_entity_id: string | null;
}

export interface EntityCandidateDecisionResult {
  dismissed: number;
  promoted: number;
  restored: number;
  entities: Entity[];
}


/** Faz 21 — bir claim'in DEĞDİĞİ entity adayı. `matched_on` hangi ad/alias üzerinden
 *  eşleştiğini söyler; Faz 20'nin alias kararları buraya aktığı için eşleşme adın kendisi
 *  olmayabilir ("GPT-6 Astra" → Astra). */
export interface MentionCandidate {
  entity_id: string;
  name: string;
  entity_type: string;
  matched_on: string;
}

export interface ClaimMentionGroup {
  claim_id: string;
  text: string;
  knowledge_state: KnowledgeState;
  confidence: number;
  source_name: string | null;
  /** Claim'in ÖZNESİ — aday değil, bağlam. Bu olmadan "değme mi özne mi" ayırt edilemez. */
  subject_name: string | null;
  candidates: MentionCandidate[];
}

export interface MentionBatchResult {
  confirmed: number;
  rejected: number;
}

export interface MentionedInClaim {
  // Backend (`recall.py`) bu alanı `id` adıyla döndürüyor; tip `claim_id` diyordu ve her
  // satırın React anahtarı `undefined` oluyordu (2026-10-18 denetimi).
  id: string;
  text: string;
  knowledge_state: KnowledgeState;
  confidence: number;
  created_at: string;
  matched_on: string;
  subject_entity_id: string | null;
  subject_entity_name: string | null;
  about_event_id: string | null;
  about_event_title: string | null;
}


/** Faz 22 — graf'ın tamamı için ilişki adayı çifti.
 *
 * `shared_claim_count` zayıf kanıt (aynı haberde iki ad anılmış olabilir),
 * `shared_event_count` güçlü (kullanıcının kendi kurduğu bağ). Ayrı tutuluyorlar. */
export interface RelationPairCandidate {
  a: { entity_id: string; name: string; entity_type: string };
  b: { entity_id: string; name: string; entity_type: string };
  shared_claim_count: number;
  shared_event_count: number;
  shared_events: { id: string; title: string }[];
  evidence: { claim_id: string; excerpt: string; kinds: string }[];
}

export interface RelationBatchResult {
  created: number;
  rejected: number;
  /** Aynı türde aktif ilişkisi zaten olan çiftler — ikiz kenar kurulmadı. */
  skipped: number;
}

export interface GraphNode {
  id: string;
  kind: "entity" | "event";
  label: string;
  entity_type: string;
  degree: number;
  knowledge_state: KnowledgeState | null;
  confidence: number | null;
}

export interface GraphEdge {
  source: string;
  target: string;
  kind: "relation" | "involved_in" | "same_as";
  label: string;
}

export interface EntityGraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

/** Faz 26 — bir claim'in dayandığı içeriğin arşiv kopyası.
 *
 * `scored` arşivin VARLIĞINDAN ayrı bir soru: arşiv her promote'ta oluşur ama confidence'a
 * ancak canlı sayfaya karşı doğrulandığında girer. İkisini tek bir alana toplamak, fazın
 * merkezi ayrımını (kayıt ≠ kanıt) arayüzde görünmez kılardı. */
export type ArchiveStatus = "ARSIVLENDI" | "DOGRULANDI" | "DEGISMIS" | "ERISILEMEDI";

export interface ArchiveRecord {
  evidence_id: string;
  claim_id: string;
  archive_url: string | null;
  archive_status: ArchiveStatus;
  archive_status_label: string;
  archive_match: number | null;
  archive_checked_at: string | null;
  archive_note: string | null;
  content_hash: string | null;
  collected_at: string | null;
  claim_headline: string | null;
  claim_state: KnowledgeState | null;
  claim_confidence: number | null;
  scored: boolean;
}

export interface ArchiveBatchResult {
  created: number;
  already: number;
  skipped: number;
  items: {
    claim_id: string;
    action: string;
    evidence_id: string | null;
    archive_status: string | null;
    reason: string | null;
  }[];
}

export interface ArchiveVerifyItem {
  evidence_id: string;
  claim_id: string;
  status: ArchiveStatus | null;
  status_label: string | null;
  match: number | null;
  note: string | null;
  scored: boolean;
  confidence_before: number | null;
  confidence_after: number | null;
  state_before: KnowledgeState | null;
  state_after: KnowledgeState | null;
}

export interface ArchiveVerifyResult {
  checked: number;
  verified: number;
  changed: number;
  unreachable: number;
  state_changes: number;
  items: ArchiveVerifyItem[];
}

/** Faz 28 — "bu doğrulanmamış claim'i şu ham gözlem doğrulayabilir" adayı.
 *
 * Faz 17'nin claim ↔ claim adayının gözlem tarafındaki karşılığı. Fark şu: burada bağlamak
 * demek gözlemi promote etmek demek, yani grafta yeni bir claim doğuyor — bu yüzden aday,
 * promote formunu doldurmaya yetecek öneriyi (kaynak + hedef) kendisi taşıyor. */
export interface ObservationCorroborationCandidate {
  claim_id: string;
  claim_text: string;
  claim_source_name: string | null;
  claim_confidence: number | null;
  claim_knowledge_state: KnowledgeState | null;
  claim_about_entity_id: string | null;
  claim_about_event_id: string | null;

  observation_id: string;
  observation_text: string;
  observation_url: string | null;
  observation_host: string | null;
  observation_dismissed: boolean;

  kind: "CORROBORATION" | "SAME_SOURCE" | "SHARED_ROOT" | "DERIVED_SUSPECT";
  rare_overlap: number;
  text_similarity: number;
  days_apart: number;
  shared_terms: string[];
  reasons: string[];
  suggested_source_id: string | null;
  suggested_source_name: string | null;
  projected_confidence: number | null;
}
