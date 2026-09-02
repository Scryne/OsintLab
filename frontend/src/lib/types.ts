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
  knowledge_state: KnowledgeState;
  confidence: number;
  valid_from: string;
  valid_to: string | null;
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
}

export interface Monitor {
  id: string;
  target_type: "Entity" | "Event" | "Investigation";
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

export interface WhyMattersReason {
  code: string;
  text: string;
  detail: Record<string, unknown>;
}

export interface EntityRecall {
  related_investigations: Pick<Investigation, "id" | "title" | "status" | "created_at">[];
  related_claims: Pick<Claim, "id" | "text" | "knowledge_state" | "confidence" | "created_at">[];
  related_events: Pick<EventItem, "id" | "title" | "event_type" | "created_at">[];
}

export interface EventRecall {
  related_investigations: Pick<Investigation, "id" | "title" | "status" | "created_at">[];
  related_claims: Pick<Claim, "id" | "text" | "knowledge_state" | "confidence" | "created_at">[];
  related_entities: Pick<Entity, "id" | "name" | "entity_type">[];
}
