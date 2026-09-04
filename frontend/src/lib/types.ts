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

export interface Evidence {
  id: string;
  evidence_type: string;
  file_path: string | null;
  content_hash: string | null;
  collected_at: string | null;
  created_at: string;
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
}

export interface Monitor {
  id: string;
  // Faz 12: "Source" — zamanlanmış tarama bildirimleri kaynak üzerinden gider.
  target_type: "Entity" | "Event" | "Investigation" | "Source";
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
  mode: "rss" | "web";
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
  })[];
  related_events: (Pick<EventItem, "id" | "title" | "event_type" | "created_at"> & {
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
