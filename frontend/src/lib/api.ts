import type {
  Claim,
  CollectorFetchResult,
  Entity,
  EntityRecall,
  EntityRelation,
  Evidence,
  EventItem,
  EventRecall,
  Hypothesis,
  InboxItem,
  Investigation,
  Monitor,
  Observation,
  ObservationPromoteResult,
  SameAsCandidate,
  SameAsPending,
  Source,
  WhyMattersReason,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8420";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/**
 * Faz 11 (dogfooding F5): API hataları ekrana ham gövdeyle basılıyordu, yani kullanıcı
 * bir allowlist reddinde `{"detail":"Reddedildi: ..."}` görüyordu. FastAPI hatayı hep
 * `detail` altında döndürür; doğrulama hatalarında ise bu bir alan listesidir.
 */
function errorMessage(body: string, fallback: string): string {
  if (!body) return fallback;
  try {
    const parsed = JSON.parse(body);
    const detail = parsed?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      const parts = detail
        .map((d) => {
          const field = Array.isArray(d?.loc) ? d.loc.filter((x: unknown) => x !== "body").join(".") : "";
          const msg = typeof d?.msg === "string" ? d.msg : "";
          return field && msg ? `${field}: ${msg}` : msg || field;
        })
        .filter(Boolean);
      if (parts.length) return parts.join("; ");
    }
    if (typeof parsed?.message === "string") return parsed.message;
  } catch {
    // JSON değilse ham metni göstermek, hiçbir şey göstermemekten iyi.
  }
  return body;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.text();
    throw new ApiError(res.status, errorMessage(body, res.statusText));
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

const get = <T>(path: string) => request<T>(path);
const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined });
const put = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "PUT", body: body ? JSON.stringify(body) : undefined });
const patch = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "PATCH", body: body ? JSON.stringify(body) : undefined });
const del = (path: string) => request<void>(path, { method: "DELETE" });

export const api = {
  health: () => get<{ status: string }>("/health"),

  entities: {
    list: () => get<Entity[]>("/entities"),
    get: (id: string) => get<Entity>(`/entities/${id}`),
    recall: (id: string) => get<{ entity_id: string } & EntityRecall>(`/entities/${id}/recall`),
    create: (payload: { entity_type: string; name: string; aliases?: string[] }) =>
      post<Entity>("/entities", payload),
    // Faz 11 (F30): backend PATCH alias'ları zaten destekliyordu, frontend hiç çağırmıyordu —
    // alias'lar pratikte hep boş kalıyordu ve SAME_AS tespitinin alias yarısı ölü koddu.
    update: (id: string, payload: { entity_type: string; name: string; aliases: string[] }) =>
      patch<Entity>(`/entities/${id}`, payload),
    createRelation: (entityId: string, payload: { to_entity_id: string; relation_type: string; confidence?: number }) =>
      post<EntityRelation & { from_entity_id: string }>(`/entities/${entityId}/relations`, payload),
    listRelations: (entityId: string) => get<EntityRelation[]>(`/entities/${entityId}/relations`),
    deleteRelation: (entityId: string, toEntityId: string, relationType: string) =>
      del(`/entities/${entityId}/relations/${toEntityId}?relation_type=${encodeURIComponent(relationType)}`),
    sameAsCandidates: (entityId: string) => get<SameAsCandidate[]>(`/entities/${entityId}/same-as/candidates`),
    suggestSameAs: (entityId: string, toEntityId: string) =>
      post<{ from_entity_id: string; to_entity_id: string; confidence: number; status: string }>(
        `/entities/${entityId}/same-as`,
        { to_entity_id: toEntityId }
      ),
    pendingSameAs: () => get<SameAsPending[]>("/entities/same-as/pending"),
    confirmSameAs: (fromId: string, toId: string) =>
      post<{ status: string }>(`/entities/same-as/${fromId}/${toId}/confirm`),
    rejectSameAs: (fromId: string, toId: string) =>
      post<{ status: string }>(`/entities/same-as/${fromId}/${toId}/reject`),
  },

  events: {
    list: () => get<EventItem[]>("/events"),
    get: (id: string) => get<EventItem>(`/events/${id}`),
    recall: (id: string) => get<{ event_id: string } & EventRecall>(`/events/${id}/recall`),
    linkEntity: (eventId: string, entityId: string, role: string) =>
      put<void>(`/events/${eventId}/entities/${entityId}`, { role }),
    linkSource: (eventId: string, sourceId: string) => put<void>(`/events/${eventId}/sources/${sourceId}`),
  },

  sources: {
    // Faz 11 (F37): Faz 6'nın otomatik türetme tespiti backend'de vardı ama arayüzden hiç
    // çağrılmıyordu — kullanıcı "bu iki haber birbirinden mi türemiş" diye soramıyordu.
    detectLineage: (claimIdA: string, claimIdB: string) =>
      post<{
        similarity: number;
        shared_agencies: string[];
        is_derived: boolean;
        method: string;
        edge_created: boolean;
      }>("/sources/lineage/detect", { claim_id_a: claimIdA, claim_id_b: claimIdB }),
    list: () => get<Source[]>("/sources"),
    get: (id: string) => get<Source>(`/sources/${id}`),
    create: (payload: { name: string; source_type: string; url?: string | null; reliability?: number }) =>
      post<Source>("/sources", payload),
    lineage: (id: string) =>
      get<{ ancestors: Source[]; descendants: Source[]; independent_root_id: string }>(
        `/sources/${id}/lineage`
      ),
    // Faz 11 (F23): otomatik tespit yalnizca metni birebir kopyalayan yayincilarda calisiyor;
    // yeniden yazan yayincilarda karari insan veriyor (Design Principle #7).
    linkDerivedFrom: (id: string, payload: { upstream_source_id: string; note?: string | null }) =>
      post<{ downstream_source_id: string; upstream_source_id: string; method: string; recomputed_claims: number }>(
        `/sources/${id}/derived-from`,
        payload
      ),
    unlinkDerivedFrom: (id: string, upstreamId: string) =>
      del(`/sources/${id}/derived-from/${upstreamId}`),
  },

  claims: {
    list: () => get<Claim[]>("/claims"),
    get: (id: string) => get<Claim>(`/claims/${id}`),
    create: (payload: {
      text: string;
      source_id: string;
      about_entity_id?: string | null;
      about_event_id?: string | null;
      evidence_ids?: string[];
      contradicting_evidence_ids?: string[];
      corroborates?: string[];
      contradicts?: string[];
      supersedes?: string | null;
    }) => post<Claim>("/claims", payload),
    explain: (id: string) =>
      get<{
        source_quality: number;
        independence: number;
        evidence: number;
        corroboration: number;
        confidence: number;
        knowledge_state: string;
      }>(`/claims/${id}/explain`),
    whyMatters: (id: string) => get<{ claim_id: string; reasons: WhyMattersReason[] }>(`/claims/${id}/why-matters`),
    // Faz 11 (F16): claim oluştuktan sonra entity/event bağını düzeltmek için.
    updateAbout: (id: string, payload: { about_entity_id?: string | null; about_event_id?: string | null }) =>
      patch<Claim>(`/claims/${id}/about`, payload),
    // Faz 11 (F26): çelişki sonradan da kurulabilmeli — çelişen ikinci haber, ilk claim
    // kaydedildikten günler sonra çıkıyor.
    addContradiction: (id: string, otherClaimId: string) =>
      post<Claim>(`/claims/${id}/contradicts`, { other_claim_id: otherClaimId }),
  },

  evidence: {
    list: () => get<Evidence[]>("/evidence"),
    get: (id: string) => get<Evidence>(`/evidence/${id}`),
    create: (payload: { evidence_type: string; file_path?: string | null; content_hash?: string | null; collected_at?: string | null }) =>
      post<Evidence>("/evidence", payload),
    linkToClaim: (evidenceId: string, claimId: string, stance: "SUPPORTS" | "CONTRADICTS") =>
      put<{ claim: Claim; evidence_id: string; stance: string }>(`/evidence/${evidenceId}/claims/${claimId}`, { stance }),
  },

  investigations: {
    list: () => get<Investigation[]>("/investigations"),
    get: (id: string) => get<Investigation>(`/investigations/${id}`),
    hypotheses: (id: string) => get<Hypothesis[]>(`/investigations/${id}/hypotheses`),
    createHypothesis: (id: string, text: string) => post<Hypothesis>(`/investigations/${id}/hypotheses`, { text }),
    findings: (id: string) =>
      get<(Pick<Claim, "id" | "text" | "knowledge_state" | "confidence"> & { validated: boolean })[]>(
        `/investigations/${id}/findings`
      ),
    transition: (id: string, to_status: string) =>
      post<Investigation>(`/investigations/${id}/transition`, { to_status }),
    // Faz 11 (F35): kapsam uçları backend'de vardı ama arayüzden hiç çağrılmıyordu — bir
    // investigation'a entity/event eklemek UI'dan mümkün değildi, okuma ucu ise hiç yoktu.
    scope: (id: string) =>
      get<{
        entities: { id: string; name: string; entity_type: string }[];
        events: { id: string; title: string; event_type: string }[];
      }>(`/investigations/${id}/scope`),
    addEntity: (id: string, entityId: string) => put<void>(`/investigations/${id}/entities/${entityId}`, {}),
    removeEntity: (id: string, entityId: string) => del(`/investigations/${id}/entities/${entityId}`),
    addEvent: (id: string, eventId: string) => put<void>(`/investigations/${id}/events/${eventId}`, {}),
    removeEvent: (id: string, eventId: string) => del(`/investigations/${id}/events/${eventId}`),
    // F36: hipoteze kanıt bağlama ucu da arayüzden hiç çağrılmıyordu — HYPOTHESIS_EVIDENCE
    // ilişkisi ve hipotez durumunun (SUPPORTED/WEAKENED) yeniden hesabı UI'dan erişilemezdi.
    linkHypothesisEvidence: (hypothesisId: string, evidenceId: string, stance: "SUPPORTS" | "WEAKENS" | "REFUTES") =>
      put<Hypothesis>(`/hypotheses/${hypothesisId}/evidence`, { evidence_id: evidenceId, stance }),
  },

  observations: {
    list: (promoted?: boolean) =>
      get<Observation[]>(`/observations${promoted === undefined ? "" : `?promoted=${promoted}`}`),
    create: (payload: { raw_content: string; observed_at?: string | null; source_url?: string | null }) =>
      post<Observation>("/observations", payload),
    promote: (
      id: string,
      payload: {
        source_id: string;
        about_entity_id?: string | null;
        about_event_id?: string | null;
        evidence_ids?: string[];
        contradicting_evidence_ids?: string[];
        corroborates?: string[];
        // Faz 11 (F26): promote'ta yoktu — toplanan veriden gelen claim'ler çelişkili
        // işaretlenemiyor, eski bir claim'in yerini alamıyordu.
        contradicts?: string[];
        supersedes?: string | null;
      }
    ) => post<ObservationPromoteResult>(`/observations/${id}/promote`, payload),
  },

  collectors: {
    allowlist: () => get<{ hostnames: string[] }>("/collectors/allowlist"),
    addAllowlist: (hostname: string) => post<{ hostnames: string[] }>("/collectors/allowlist", { hostname }),
    removeAllowlist: (hostname: string) => del(`/collectors/allowlist/${encodeURIComponent(hostname)}`),
    fetch: (url: string, mode: "rss" | "web", opts?: { limit?: number; since_days?: number | null }) =>
      post<CollectorFetchResult>("/collectors/fetch", {
        url,
        mode,
        ...(opts?.limit ? { limit: opts.limit } : {}),
        ...(opts?.since_days ? { since_days: opts.since_days } : {}),
      }),
  },

  monitors: {
    list: (active?: boolean) => get<Monitor[]>(`/monitors${active === undefined ? "" : `?active=${active}`}`),
    create: (payload: { target_type: string; target_id: string; label?: string | null }) =>
      post<Monitor>("/monitors", payload),
    delete: (id: string) => del(`/monitors/${id}`),
  },

  inbox: {
    list: (params?: { min_priority?: string; status?: string }) => {
      const qs = new URLSearchParams();
      if (params?.min_priority) qs.set("min_priority", params.min_priority);
      if (params?.status) qs.set("status", params.status);
      const suffix = qs.toString() ? `?${qs.toString()}` : "";
      return get<InboxItem[]>(`/inbox${suffix}`);
    },
    updateStatus: (id: string, status: string) => patch<InboxItem>(`/inbox/${id}`, { status }),
    getSettings: () => get<{ min_priority: string }>("/inbox/settings"),
    updateSettings: (min_priority: string) => put<{ min_priority: string }>("/inbox/settings", { min_priority }),
  },

  intelligence: {
    diff: (days = 30) =>
      get<Record<string, unknown>>(`/intelligence/diff?days=${days}`),
  },
};
