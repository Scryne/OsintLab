import type {
  ArchiveBatchResult,
  ObservationCorroborationCandidate,
  ArchiveRecord,
  ArchiveVerifyResult,
  Claim,
  ClaimExplain,
  ClaimLinkBatchResult,
  CollectorFetchResult,
  CorroborationCandidate,
  Entity,
  EntityRecall,
  EntityCandidateDecisionResult,
  EntityGraphData,
  EntityRelation,
  Evidence,
  ExtractedEntityCandidate,
  EvidenceExtraction,
  EvidenceFingerprint,
  EvidenceVaultItem,
  EventCandidate,
  EventFromClusterResult,
  EventItem,
  EventRecall,
  Hypothesis,
  HypothesisEvidenceLink,
  InboxItem,
  Investigation,
  InvestigationWorkspace,
  ClaimMentionGroup,
  MentionBatchResult,
  Monitor,
  Observation,
  ObservationDismissResult,
  ObservationPromoteBatchResult,
  ObservationPromoteResult,
  ObservationQueue,
  RelationCandidate,
  RelationBatchResult,
  RelationPairCandidate,
  SameAsCandidate,
  SameAsPending,
  LineageNode,
  ScanRunResult,
  ScanSchedule,
  SourceClaim,
  Source,
  WhyMattersReason,
} from "./types";
import type {
  BulkJob,
  DatasetStatus,
  DorkRecipe,
  EnrichmentModule,
  EnrichmentRun,
  ExtractedSelector,
  PivotGraph,
  Selector,
  SelectorDetail,
  SelectorDetect,
  SelectorKindCount,
  SelectorList,
  ChronoWindow,
  SearchResult,
  SunResult,
  ToolCatalog,
  ToolLink,
} from "./types-pivot";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8420";

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
const del = <T = void>(path: string) => request<T>(path, { method: "DELETE" });

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
    // Faz 19: birlikte geçen entity'ler ilişki adayı olarak önerilir. Öneridir — türü
    // kullanıcı yazar, sistem tahmin etmez.
    relationCandidates: (entityId: string) =>
      get<RelationCandidate[]>(`/entities/${entityId}/relation-candidates`),
    // Faz 22: graf'ın tamamı için aday çiftler — entity entity gezmek kararı pahalı yapıyordu.
    relationPairCandidates: () => get<RelationPairCandidate[]>("/entities/relations/candidates"),
    decideRelations: (
      decisions: {
        from_entity_id: string;
        to_entity_id: string;
        action: "CREATE" | "REJECT";
        relation_type?: string;
        confidence?: number;
      }[]
    ) => post<RelationBatchResult>("/entities/relations/batch", { decisions }),
    graph: () => get<EntityGraphData>("/entities/relations/graph"),
    deleteRelation: (entityId: string, toEntityId: string, relationType: string) =>
      del(`/entities/${entityId}/relations/${toEntityId}?relation_type=${encodeURIComponent(relationType)}`),
    sameAsCandidates: (entityId: string) => get<SameAsCandidate[]>(`/entities/${entityId}/same-as/candidates`),
    suggestSameAs: (entityId: string, toEntityId: string) =>
      post<{ from_entity_id: string; to_entity_id: string; confidence: number; status: string }>(
        `/entities/${entityId}/same-as`,
        { to_entity_id: toEntityId }
      ),
    pendingSameAs: () => get<SameAsPending[]>("/entities/same-as/pending"),
    // Faz 20: claim metinlerinden deterministik entity adayı çıkarma. Adaylar saklanmaz,
    // her çağrıda yeniden çıkarılır; saklanan tek şey karardır.
    extractedCandidates: (includeDecided = false) =>
      get<ExtractedEntityCandidate[]>(`/entities/candidates?include_decided=${includeDecided}`),
    dismissCandidates: (keys: string[]) =>
      post<EntityCandidateDecisionResult>("/entities/candidates/dismiss", { keys }),
    restoreCandidates: (keys: string[]) =>
      post<EntityCandidateDecisionResult>("/entities/candidates/restore", { keys }),
    promoteCandidates: (
      items: { key: string; name?: string; entity_type: string; aliases?: string[] }[]
    ) => post<EntityCandidateDecisionResult>("/entities/candidates/promote", { items }),
    confirmSameAs: (fromId: string, toId: string) =>
      post<{ status: string }>(`/entities/same-as/${fromId}/${toId}/confirm`),
    rejectSameAs: (fromId: string, toId: string) =>
      post<{ status: string }>(`/entities/same-as/${fromId}/${toId}/reject`),
  },

  events: {
    list: () => get<EventItem[]>("/events"),
    get: (id: string) => get<EventItem>(`/events/${id}`),
    create: (payload: {
      title: string;
      event_type: string;
      occurred_at?: string | null;
      location?: string | null;
    }) => post<EventItem>("/events", payload),
    update: (
      id: string,
      payload: { title?: string; event_type?: string; occurred_at?: string | null; location?: string | null }
    ) => patch<EventItem>(`/events/${id}`, payload),
    recall: (id: string) => get<{ event_id: string } & EventRecall>(`/events/${id}/recall`),
    // Faz 18: doğrulama kümelerinden türetilen olay adayları. Öneridir — başlığı ve
    // kümenin sınırını kullanıcı belirler (Design Principle #7).
    candidates: (minSize = 2) => get<EventCandidate[]>(`/events/candidates?min_size=${minSize}`),
    fromCluster: (payload: {
      title: string;
      event_type: string;
      occurred_at?: string | null;
      location?: string | null;
      claim_ids: string[];
      carry_entities?: boolean;
      entity_role?: string;
    }) => post<EventFromClusterResult>("/events/from-cluster", payload),
    linkClaim: (eventId: string, claimId: string) => put<EventItem>(`/events/${eventId}/claims/${claimId}`),
    unlinkClaim: (eventId: string, claimId: string) => del(`/events/${eventId}/claims/${claimId}`),
    linkEntity: (eventId: string, entityId: string, role: string) =>
      put<void>(`/events/${eventId}/entities/${entityId}`, { role }),
    unlinkEntity: (eventId: string, entityId: string) => del(`/events/${eventId}/entities/${entityId}`),
    linkSource: (eventId: string, sourceId: string) => put<void>(`/events/${eventId}/sources/${sourceId}`),
    delete: (id: string) => del(`/events/${id}`),
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
    // `depth` = kac hop uzakta (Faz 13'te eklendi; oncesinde sira tanimsizdi, zincir
    // gosterilemiyordu — yalnizca kume).
    lineage: (id: string) =>
      get<{
        ancestors: LineageNode[];
        descendants: LineageNode[];
        independent_root_id: string;
      }>(`/sources/${id}/lineage`),
    // Faz 13: bu sorgu bugüne kadar yalnizca vault render'inda vardi; arayuz "bu kaynak neyi
    // iddia etti" sorusunu hic soramiyordu.
    claims: (id: string) => get<SourceClaim[]>(`/sources/${id}/claims`),
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
    /** Faz 17 — "bu iki claim aynı olayı anlatıyor" adayları, gerekçeleriyle ve
     * sınıflandırılmış. `kind` alanına bak: yalnızca CORROBORATION bağlanabilir. */
    corroborationCandidates: (opts?: { claimId?: string; limit?: number }) => {
      const qs = new URLSearchParams();
      if (opts?.claimId) qs.set("claim_id", opts.claimId);
      if (opts?.limit !== undefined) qs.set("limit", String(opts.limit));
      const suffix = qs.toString() ? `?${qs.toString()}` : "";
      return get<CorroborationCandidate[]>(`/claims/corroboration/candidates${suffix}`);
    },
    /** Doğrulama ve çelişki AYNI uçtan: aynı olayı anlatan iki claim birbirini
     * doğrulayabileceği gibi çelişebilir de, ikisi de aynı aday listesinden çıkıyor. */
    linkBatch: (pairs: { claim_a_id: string; claim_b_id: string; link: "CORROBORATES" | "CONTRADICTS" }[]) =>
      post<ClaimLinkBatchResult>("/claims/links-batch", { pairs }),
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
    explain: (id: string) => get<ClaimExplain>(`/claims/${id}/explain`),
    whyMatters: (id: string) => get<{ claim_id: string; reasons: WhyMattersReason[] }>(`/claims/${id}/why-matters`),
    // Faz 21: claim'in DEĞDİĞİ entity'ler — öznesinden (`about`) ayrı bir ilişki.
    mentionCandidates: () => get<ClaimMentionGroup[]>("/claims/mentions/candidates"),
    decideMentions: (
      decisions: { claim_id: string; entity_id: string; action: "CONFIRM" | "REJECT"; matched_on?: string }[]
    ) => post<MentionBatchResult>("/claims/mentions/batch", { decisions }),
    mentions: (id: string) =>
      get<{ entity_id: string; name: string; entity_type: string; matched_on: string }[]>(
        `/claims/${id}/mentions`
      ),
    removeMention: (claimId: string, entityId: string) => del(`/claims/${claimId}/mentions/${entityId}`),
    // Faz 11 (F16): claim oluştuktan sonra entity/event bağını düzeltmek için.
    updateAbout: (id: string, payload: { about_entity_id?: string | null; about_event_id?: string | null }) =>
      patch<Claim>(`/claims/${id}/about`, payload),
    // Faz 11 (F26): çelişki sonradan da kurulabilmeli — çelişen ikinci haber, ilk claim
    // kaydedildikten günler sonra çıkıyor.
    addContradiction: (id: string, otherClaimId: string) =>
      post<Claim>(`/claims/${id}/contradicts`, { other_claim_id: otherClaimId }),
    // Faz 28 — ters yonlu arama: bu doğrulanmamış claim'i hangi ham gözlem doğrulayabilir.
    // Faz 17'nin claim ↔ claim ekranı ikinci claim'in zaten var olmasını gerektiriyordu.
    observationCandidates: (opts?: {
      claimId?: string;
      includeCorroborated?: boolean;
      includeDismissed?: boolean;
      limit?: number;
    }) => {
      const q = new URLSearchParams();
      if (opts?.claimId) q.set("claim_id", opts.claimId);
      if (opts?.includeCorroborated) q.set("include_corroborated", "true");
      if (opts?.includeDismissed === false) q.set("include_dismissed", "false");
      q.set("limit", String(opts?.limit ?? 300));
      return get<ObservationCorroborationCandidate[]>(
        `/claims/corroboration/observation-candidates?${q}`
      );
    },
    // Faz 11 (F45): supersede sonradan da bildirilebilmeli — gerçek araştırmada yeni bilgi
    // eskisi kaydedildikten sonra çıkıyor, bazen de eskisi sonradan kaydediliyor.
    addSupersede: (id: string, supersedesClaimId: string) =>
      post<Claim>(`/claims/${id}/supersedes`, { supersedes_claim_id: supersedesClaimId }),
  },

  evidence: {
    // Faz 34 — görsel analizi (EXIF, GPS, algısal hash, üretim izleri). Özet şekli dosyaya göre
    // değişir; bileşen alanları kendisi okur.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    media: (id: string) => get<{ evidence_id: string; analysis: any; similar: { evidence_id: string; file_path: string; distance: number }[] }>(`/evidence/${id}/media`),
    // Faz 13: liste artık bağlı claim'leri ve dosyanın gerçekten yerinde olup olmadığını da
    // taşıyor (Evidence Vault). Ek alanlar geriye dönük uyumlu — eski çağıranlar etkilenmiyor.
    list: () => get<EvidenceVaultItem[]>("/evidence"),
    claims: (id: string) =>
      get<EvidenceVaultItem["linked_claims"]>(`/evidence/${id}/claims`),
    // Dosya indirme bir <a href> ile yapılıyor; burada yalnızca adresi üretiyoruz.
    fileUrl: (id: string) => `${API_BASE}/evidence/${id}/file`,
    // Faz 15.1 (DOCINT): belgeden ne çıkarıldığı — durum, metadata, önizleme.
    extraction: (id: string) => get<EvidenceExtraction>(`/evidence/${id}/extraction`),
    // Tam metin ayrı bir adres: tek bir belge milyonlarca karakter olabiliyor, liste
    // yanıtına konamaz. Yeni sekmede açılıyor, indirilmiyor.
    textUrl: (id: string) => `${API_BASE}/evidence/${id}/text`,
    // Yeniden çıkarma kuyruğuna alır. İki gerçek ihtiyaç: 15.1'den önce yüklenmiş kanıtlar
    // hiç işlenmemiş durumda, ve başarısız bir belge için tekrar denemek gerekebiliyor.
    extract: (id: string) => post<{ status: string; status_label: string; queue_depth: number }>(
      `/evidence/${id}/extract`,
      {}
    ),
    // Faz 15.2: belgenin seçilen sayfa aralığından Observation üretir. Tüm belge değil —
    // promote gözlemin metnini doğrudan claim metni yapıyor.
    createObservation: (id: string, payload: { page_from: number; page_to: number }) =>
      post<Observation>(`/evidence/${id}/observations`, payload),
    // Faz 15.3 — belgenin üretildiği ortamın izi (metadata), OSINT anlamına göre gruplanmış.
    fingerprint: (id: string) => get<EvidenceFingerprint>(`/evidence/${id}/fingerprint`),
    // Bağı kullanıcı kurar (Design Principle #7); sistem yalnızca olası eşleşmeyi öne alır.
    linkFingerprint: (id: string, entityId: string, field: string) =>
      put<EvidenceFingerprint>(`/evidence/${id}/fingerprint/${entityId}`, { field }),
    unlinkFingerprint: (id: string, entityId: string, field: string) =>
      del(`/evidence/${id}/fingerprint/${entityId}?field=${encodeURIComponent(field)}`),
    // Faz 15.4 — belgeyi metin katmanından değil görüntüden okur. Açık bir tercih: taranmış
    // 492 sayfalık bir belge dakikalar sürer, sürpriz olarak başlatılmamalı. OCR kurulu
    // değilse uç 503 ile SEBEBİ söyler (kurulum komutu dahil).
    ocr: (id: string) => post<{ status: string; status_label: string; lang: string | null }>(
      `/evidence/${id}/ocr`,
      {}
    ),
    upload: async (payload: { file: File; evidence_type: string; collected_at?: string | null }) => {
      const form = new FormData();
      form.append("file", payload.file);
      form.append("evidence_type", payload.evidence_type);
      if (payload.collected_at) form.append("collected_at", payload.collected_at);
      // FormData gönderirken Content-Type'ı ELLE koymuyoruz: tarayıcının multipart
      // boundary'yi kendisi eklemesi gerekiyor. request() her zaman application/json
      // koyduğu için burada fetch doğrudan kullanılıyor.
      const res = await fetch(`${API_BASE}/evidence/upload`, { method: "POST", body: form });
      if (!res.ok) throw new ApiError(res.status, errorMessage(await res.text(), res.statusText));
      return (await res.json()) as Evidence;
    },
    get: (id: string) => get<Evidence>(`/evidence/${id}`),
    create: (payload: { evidence_type: string; file_path?: string | null; content_hash?: string | null; collected_at?: string | null }) =>
      post<Evidence>("/evidence", payload),
    linkToClaim: (evidenceId: string, claimId: string, stance: "SUPPORTS" | "CONTRADICTS") =>
      put<{ claim: Claim; evidence_id: string; stance: string }>(`/evidence/${evidenceId}/claims/${claimId}`, { stance }),
  },

  investigations: {
    list: () => get<Investigation[]>("/investigations"),
    get: (id: string) => get<Investigation>(`/investigations/${id}`),
    // Faz 11 (F38): `POST /investigations` backend'de vardı ama arayüzde ne api metodu ne de
    // buton vardı — investigation UI'dan hiç açılamıyordu. İlk taramada gözden kaçtı çünkü
    // uç kapsaması YOL düzeyinde kontrol edilmişti: GET /investigations çağrıldığı için yol
    // "kapsanmış" göründü. Metot düzeyinde tarayınca çıktı.
    create: (payload: { title: string; research_question: string }) =>
      post<Investigation>("/investigations", payload),
    addFinding: (id: string, claimId: string) => put<void>(`/investigations/${id}/findings/${claimId}`, {}),
    // v6 — Rakip Hipotezler Analizi matrisi.
    ach: (id: string) =>
      get<{
        hypotheses: { id: string; text: string; status: string; inconsistency: number; supporting: number; unassessed: number }[];
        evidence: { id: string; name: string; evidence_type: string; cells: Record<string, string | null>; diagnostic: boolean }[];
        ranking: string[];
        unassessed_cells: number;
      }>(`/investigations/${id}/ach`),
    removeFinding: (id: string, claimId: string) => del(`/investigations/${id}/findings/${claimId}`),
    hypotheses: (id: string) => get<Hypothesis[]>(`/investigations/${id}/hypotheses`),
    createHypothesis: (id: string, text: string) => post<Hypothesis>(`/investigations/${id}/hypotheses`, { text }),
    // `headline` uçta üretiliyor (F46'nın kalıcı çözümü): claim metni "başlık + özet"
    // biçiminde tek bir string, her render eden yerin ilk satırı kendi kesmesi dördüncü kez
    // aynı bozuk çıktıyı üretmişti.
    findings: (id: string) =>
      get<
        (Pick<Claim, "id" | "text" | "knowledge_state" | "confidence"> & {
          validated: boolean;
          headline: string;
        })[]
      >(`/investigations/${id}/findings`),
    transition: (id: string, to_status: string) =>
      post<Investigation>(`/investigations/${id}/transition`, { to_status }),
    // Faz 13 (madde 30): zincirin tamamı tek çağrıda — ara adımlar graf'tan türetiliyor.
    workspace: (id: string) => get<InvestigationWorkspace>(`/investigations/${id}/workspace`),
    updateNarrative: (id: string, payload: { analysis?: string; conclusion?: string }) =>
      patch<Investigation>(`/investigations/${id}/narrative`, payload),
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
    // Hipotezin durumunu belirleyen kanıtlar — "neden REFUTED?" sorusunun cevabı. Bir kanıtın
    // bir hipoteze tek duruşu var; yeniden bağlamak duruşu değiştirir, kaldırmak geri alır.
    hypothesisEvidence: (hypothesisId: string) =>
      get<HypothesisEvidenceLink[]>(`/hypotheses/${hypothesisId}/evidence`),
    unlinkHypothesisEvidence: (hypothesisId: string, evidenceId: string) =>
      del<Hypothesis>(`/hypotheses/${hypothesisId}/evidence/${evidenceId}`),
  },

  observations: {
    // `ids` — F58: Inbox bildirimi "17 yeni içerik" diyor ve hangi gözlemler olduğunu
    // biliyor; bu parametre olmadan o gözlemlere gitmenin yolu yoktu.
    list: (opts?: { promoted?: boolean; ids?: string[]; dismissed?: boolean }) => {
      const qs = new URLSearchParams();
      if (opts?.promoted !== undefined) qs.set("promoted", String(opts.promoted));
      if (opts?.ids?.length) qs.set("ids", opts.ids.join(","));
      // Faz 16: elenen gözlem silinmiyor, sadece işaretleniyor — "Bekliyor" sekmesinin
      // doğru cevap vermesi için ayrıca filtrelenmesi gerekiyor.
      if (opts?.dismissed !== undefined) qs.set("dismissed", String(opts.dismissed));
      const suffix = qs.toString() ? `?${qs.toString()}` : "";
      return get<Observation[]>(`/observations${suffix}`);
    },
    // Faz 16 — değerlendirmeyi bekleyen gözlemler, sinyale göre sıralı + kuyruk sağlığı.
    queue: (opts?: { limit?: number; offset?: number; host?: string; maxScore?: number; minScore?: number }) => {
      const qs = new URLSearchParams();
      if (opts?.limit !== undefined) qs.set("limit", String(opts.limit));
      if (opts?.offset !== undefined) qs.set("offset", String(opts.offset));
      if (opts?.host) qs.set("host", opts.host);
      if (opts?.maxScore !== undefined) qs.set("max_score", String(opts.maxScore));
      if (opts?.minScore !== undefined) qs.set("min_score", String(opts.minScore));
      const suffix = qs.toString() ? `?${qs.toString()}` : "";
      return get<ObservationQueue>(`/observations/queue${suffix}`);
    },
    // Nav rozeti: yalnız bekleyen sayısı, skorlamasız (tarama sürerken /queue her soruda baştan skorluyordu).
    queueCount: () => get<{ pending: number }>("/observations/queue/count"),
    dismiss: (observationIds: string[], reason?: string | null) =>
      post<ObservationDismissResult>("/observations/dismiss", {
        observation_ids: observationIds,
        reason: reason ?? null,
      }),
    undismiss: (observationIds: string[]) =>
      post<ObservationDismissResult>("/observations/undismiss", { observation_ids: observationIds }),
    /** Faz 16 (ikinci tur) — seçilen gözlemleri TEK kararla promote eder. `sourceId`/`entityId`
     * verilmezse her kayıt kuyrukta gösterilen KENDİ önerisini kullanır. Otomatik bir kural
     * değil: kümeyi kullanıcı seçiyor (Design Principle #7). */
    promoteBatch: (payload: {
      observationIds: string[];
      sourceId?: string | null;
      entityId?: string | null;
      requireEntity?: boolean;
    }) =>
      post<ObservationPromoteBatchResult>("/observations/promote-batch", {
        observation_ids: payload.observationIds,
        source_id: payload.sourceId ?? null,
        about_entity_id: payload.entityId ?? null,
        require_entity: payload.requireEntity ?? true,
      }),
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
    fetch: (url: string, mode: "rss" | "web" | "telegram", opts?: { limit?: number; since_days?: number | null }) =>
      post<CollectorFetchResult>("/collectors/fetch", {
        url,
        mode,
        ...(opts?.limit ? { limit: opts.limit } : {}),
        ...(opts?.since_days ? { since_days: opts.since_days } : {}),
      }),
    // Faz 12 — zamanlanmış tarama.
    schedules: (active?: boolean) =>
      get<ScanSchedule[]>(`/collectors/schedules${active === undefined ? "" : `?active=${active}`}`),
    createSchedule: (payload: {
      source_id: string;
      url?: string | null;
      mode?: "rss" | "web" | "telegram";
      interval_minutes?: number;
      item_limit?: number;
      since_days?: number | null;
      label?: string | null;
      watch?: boolean;
    }) => post<ScanSchedule>("/collectors/schedules", payload),
    updateSchedule: (
      id: string,
      payload: { interval_minutes?: number; item_limit?: number; since_days?: number | null; label?: string | null; active?: boolean }
    ) => patch<ScanSchedule>(`/collectors/schedules/${id}`, payload),
    deleteSchedule: (id: string) => del(`/collectors/schedules/${id}`),
    runSchedule: (id: string) => post<ScanRunResult>(`/collectors/schedules/${id}/run`),
  },

  // Faz 26 — kaynak arşivi. Arşivin kendisi promote'ta otomatik oluşuyor; buradaki uçlar
  // geri doldurma ve canlı sayfaya karşı doğrulama içindir.
  archive: {
    list: () => get<ArchiveRecord[]>("/archive"),
    pending: () => get<string[]>("/archive/pending"),
    forClaim: (claimId: string) => get<ArchiveRecord>(`/archive/claims/${claimId}`),
    create: (claimIds?: string[]) =>
      post<ArchiveBatchResult>("/archive/create", { claim_ids: claimIds ?? null }),
    // Doğrulama AĞ kullanır ve sayfa başına saniyeler sürebilir; arayüz bunu tek tek ya da
    // seçili kayıtlar için tetikliyor, kendiliğinden değil.
    verify: (claimIds?: string[]) =>
      post<ArchiveVerifyResult>("/archive/verify", { claim_ids: claimIds ?? null }),
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

  // Faz 29 — seçici katmanı. Kimlik `tür:değer` ve değer `/` içerebilir (URL): yol parçası
  // olarak her zaman tamamen kodlanır.
  selectors: {
    list: (params?: { kind?: string; q?: string; sort?: string; limit?: number; offset?: number; include_ignored?: boolean; flag?: "kev" }) => {
      const qs = new URLSearchParams();
      for (const [k, v] of Object.entries(params ?? {})) if (v !== undefined && v !== "") qs.set(k, String(v));
      return get<SelectorList>(`/selectors${qs.toString() ? `?${qs}` : ""}`);
    },
    kinds: () => get<SelectorKindCount[]>("/selectors/kinds"),
    detect: (value: string) => post<SelectorDetect>("/selectors/detect", { value }),
    extract: (text: string) => post<ExtractedSelector[]>("/selectors/extract", { text }),
    create: (value: string, note = "") => post<Selector>("/selectors", { value, note }),
    detail: (id: string) => get<SelectorDetail>(`/selectors/${encodeURIComponent(id)}/detail`),
    graph: (id: string, depth = 2) => get<PivotGraph>(`/selectors/${encodeURIComponent(id)}/graph?depth=${depth}`),
    update: (id: string, payload: { status?: "ACTIVE" | "IGNORED"; note?: string }) =>
      patch<Selector>(`/selectors/${encodeURIComponent(id)}`, payload),
    linkEntity: (id: string, entityId: string, note = "") =>
      post<void>(`/selectors/${encodeURIComponent(id)}/entities`, { entity_id: entityId, note }),
    unlinkEntity: (id: string, entityId: string) =>
      del(`/selectors/${encodeURIComponent(id)}/entities/${entityId}`),
    forEntity: (entityId: string) => get<(Selector & { link_note: string | null })[]>(`/entities/${entityId}/selectors`),
    forClaim: (claimId: string) => get<Selector[]>(`/claims/${claimId}/selectors`),
    claimGrade: (claimId: string) =>
      get<{ code: string; source: string; source_label: string; info: number; info_label: string }>(`/claims/${claimId}/grade`),
    watchCheck: (id: string) => post<{ modules: string[]; notices: unknown[] }>(`/selectors/${encodeURIComponent(id)}/watch-check`),
    reindex: () =>
      post<{ observations_scanned: number; evidence_scanned: number; new_sightings: number; selectors_total: number; duration_seconds: number }>(
        "/selectors/reindex"
      ),
  },

  // Faz 30 — zenginleştirme. Arayüz koşuyu `wait: false` ile başlatır ve yoklar: Wayback ve
  // crt.sh gibi kaynaklar ölçümde dakikaları buldu.
  enrichment: {
    modules: () => get<EnrichmentModule[]>("/enrichment/modules"),
    toggle: (name: string, enabled: boolean) => patch<EnrichmentModule>(`/enrichment/modules/${name}`, { enabled }),
    forTarget: (targetId: string) => get<EnrichmentModule[]>(`/enrichment/targets/${encodeURIComponent(targetId)}/modules`),
    runsFor: (targetId: string) => get<EnrichmentRun[]>(`/enrichment/targets/${encodeURIComponent(targetId)}/runs`),
    run: (module: string, targetId: string, opts?: { force?: boolean; confirm_active?: boolean }) =>
      post<EnrichmentRun>("/enrichment/run", { module, target_id: targetId, wait: false, ...opts }),
    getRun: (id: string) => get<EnrichmentRun>(`/enrichment/runs/${id}`),
    raw: (id: string) => get<{ integrity_ok: boolean; record: Record<string, unknown> }>(`/enrichment/runs/${id}/raw`),
    recent: (limit = 100) => get<EnrichmentRun[]>(`/enrichment/runs?limit=${limit}`),
    toObservation: (id: string) => post<Observation>(`/enrichment/runs/${id}/observation`),
    datasets: () => get<DatasetStatus[]>("/enrichment/datasets"),
    exploited: (limit = 50) =>
      get<{
        id: string;
        cve: string;
        vendor: string | null;
        product: string | null;
        name: string | null;
        date_added: string | null;
        known_ransomware: boolean;
        epss: number | null;
        epss_percentile: number | null;
        sightings: number;
        last_seen: string | null;
      }[]>(`/enrichment/exploited?limit=${limit}`),
    downloadDataset: (name: string) => post<{ name: string; started: boolean }>(`/enrichment/datasets/${name}/download`),
    bulkStatus: () => get<BulkJob>("/enrichment/bulk"),
    bulk: (module: string, kind: string, only_missing = true) => post<BulkJob>("/enrichment/bulk", { module, kind, only_missing }),
    cancelBulk: () => post<BulkJob>("/enrichment/bulk/cancel"),
  },

  // Faz 32 — dış araç kataloğu. Backend bu araçlara istek ATMAZ; bağlantılar tarayıcıda açılır.
  tools: {
    catalog: () => get<ToolCatalog>("/tools"),
    links: (kind: string, value: string) =>
      get<ToolLink[]>(`/tools/links?kind=${kind}&value=${encodeURIComponent(value)}`),
    dorks: (kind: string, value: string) =>
      get<DorkRecipe[]>(`/tools/dorks?kind=${kind}&value=${encodeURIComponent(value)}`),
  },

  // Faz 33 — komut paleti: seçici tanıma + gruplu arama.
  search: (q: string) => get<SearchResult>(`/search?q=${encodeURIComponent(q)}`),

  // Faz 34 — güneş konumu ve kronolokasyon (yerel hesap, ağ yok).
  sun: (lat: number, lon: number, opts?: { at?: string; day?: string }) => {
    const qs = new URLSearchParams({ lat: String(lat), lon: String(lon) });
    if (opts?.at) qs.set("at", opts.at);
    if (opts?.day) qs.set("day", opts.day);
    return get<SunResult>(`/tools/sun?${qs}`);
  },
  chronolocate: (payload: {
    lat: number;
    lon: number;
    day: string;
    shadow_direction?: number | null;
    length_ratio?: number | null;
    direction_tolerance?: number;
    ratio_tolerance?: number;
  }) => post<{ windows: ChronoWindow[] }>("/tools/chronolocate", payload),

  intelligence: {
    diff: (days = 30) =>
      get<Record<string, unknown>>(`/intelligence/diff?days=${days}`),
  },
};
