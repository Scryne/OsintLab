import type {
  Claim,
  Entity,
  EntityRecall,
  EventItem,
  EventRecall,
  Hypothesis,
  InboxItem,
  Investigation,
  Monitor,
  Observation,
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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.text();
    throw new ApiError(res.status, body || res.statusText);
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
  },

  events: {
    list: () => get<EventItem[]>("/events"),
    get: (id: string) => get<EventItem>(`/events/${id}`),
    recall: (id: string) => get<{ event_id: string } & EventRecall>(`/events/${id}/recall`),
    linkEntity: (eventId: string, entityId: string, role: string) =>
      put<void>(`/events/${eventId}/entities/${entityId}`, { role }),
  },

  sources: {
    list: () => get<Source[]>("/sources"),
    get: (id: string) => get<Source>(`/sources/${id}`),
    lineage: (id: string) =>
      get<{ ancestors: Source[]; descendants: Source[]; independent_root_id: string }>(
        `/sources/${id}/lineage`
      ),
  },

  claims: {
    list: () => get<Claim[]>("/claims"),
    get: (id: string) => get<Claim>(`/claims/${id}`),
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
  },

  investigations: {
    list: () => get<Investigation[]>("/investigations"),
    get: (id: string) => get<Investigation>(`/investigations/${id}`),
    hypotheses: (id: string) => get<Hypothesis[]>(`/investigations/${id}/hypotheses`),
    findings: (id: string) =>
      get<(Pick<Claim, "id" | "text" | "knowledge_state" | "confidence"> & { validated: boolean })[]>(
        `/investigations/${id}/findings`
      ),
    transition: (id: string, to_status: string) =>
      post<Investigation>(`/investigations/${id}/transition`, { to_status }),
  },

  observations: {
    list: (promoted?: boolean) =>
      get<Observation[]>(`/observations${promoted === undefined ? "" : `?promoted=${promoted}`}`),
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
