// Faz 29-35 — seçici, zenginleştirme, pivot ve araç kataloğu tipleri.
// `types.ts` 900 satırı geçti; yeni katman kendi dosyasında (backend'deki `models_pivot.py` gibi).

export type SelectorKind =
  | "domain" | "ip" | "url" | "email" | "md5" | "sha1" | "sha256"
  | "cve" | "attack" | "asn" | "btc" | "eth" | "coord";

export interface Selector {
  id: string;
  kind: SelectorKind;
  value: string;
  status: "ACTIVE" | "IGNORED";
  origin: "extracted" | "manual" | "enrichment";
  note: string | null;
  created_at: string;
}

export interface SelectorListItem extends Selector {
  observation_count: number;
  evidence_count: number;
  enrichment_count: number;
  entity_count: number;
  first_seen: string | null;
  last_seen: string | null;
  flags: string[];
}

export interface SelectorList {
  total: number;
  items: SelectorListItem[];
}

export interface SelectorKindCount {
  kind: SelectorKind;
  label: string;
  count: number;
}

export interface SelectorDetect {
  kind: SelectorKind | null;
  value: string | null;
  label: string | null;
  id: string | null;
  exists: boolean;
}

export interface ExtractedSelector {
  id: string;
  kind: SelectorKind;
  label: string;
  value: string;
  context: string;
  defanged: boolean;
  occurrences: number;
}

export interface SelectorSighting {
  observation_id: string;
  source_url: string | null;
  observed_at: string | null;
  promoted: boolean | null;
  context: string | null;
  defanged: boolean | null;
  occurrences: number | null;
  claim_id: string | null;
  claim_state: string | null;
}

export interface SelectorPivot {
  id: string;
  kind: SelectorKind;
  value: string;
  relation: string;
  module: string | null;
  run_id: string | null;
  first_seen: string | null;
  last_seen: string | null;
  direction: "in" | "out";
}

export interface SelectorDetail {
  selector: Selector;
  label: string;
  observation_count: number;
  source_hosts: string[];
  sightings: SelectorSighting[];
  documents: {
    evidence_id: string;
    file_path: string | null;
    evidence_type: string | null;
    context: string | null;
    defanged: boolean | null;
    occurrences: number | null;
  }[];
  entities: { id: string; name: string; entity_type: string; note: string | null; linked_at: string | null }[];
  pivots: SelectorPivot[];
  co_occurring: { id: string; kind: SelectorKind; value: string; shared: number }[];
}

export interface PivotGraphNode {
  id: string;
  kind: SelectorKind | "entity";
  value: string;
  level: number;
  type: "selector" | "entity";
  entity_type?: string;
}

export interface PivotGraph {
  root: string;
  nodes: PivotGraphNode[];
  edges: { source: string; target: string; relation: string; module: string | null }[];
  truncated: boolean;
}

export type Opsec = "PASSIVE" | "ACTIVE" | "LOCAL";

export interface EnrichmentRun {
  id: string;
  module: string;
  module_label: string;
  target_id: string;
  target_type: "selector" | "entity" | "claim";
  status: "RUNNING" | "DONE" | "FAILED";
  opsec: Opsec;
  request_url: string | null;
  raw_path: string | null;
  raw_sha256: string | null;
  // Modüle göre şekil değiştirir — her özet bileşeni kendi modülünün alanlarını okur.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  summary: Record<string, any> | null;
  error: string | null;
  started_at: string;
  finished_at: string | null;
  cached?: boolean;
  pivots?: { from_id: string; to_id: string; to_kind: SelectorKind; to_value: string; from_value: string; relation: string }[];
}

export interface EnrichmentModule {
  name: string;
  label: string;
  provider: string;
  description: string;
  target: "selector" | "entity" | "claim";
  kinds: SelectorKind[];
  kind_labels: string[];
  opsec: Opsec;
  opsec_note: string;
  hosts: string[];
  cache_hours: number;
  docs_url: string;
  terms_note: string;
  datasets: string[];
  enabled: boolean;
  last_run?: EnrichmentRun | null;
}

export interface DatasetStatus {
  name: string;
  label: string;
  provider: string;
  license: string;
  sources: string[];
  refresh_hours: number;
  downloaded: boolean;
  stale: boolean;
  downloading: boolean;
  last_error: string | null;
  downloaded_at?: string;
  records?: number;
  bytes?: number;
  sha256?: string | Record<string, string>;
}

export interface BulkJob {
  running: boolean;
  module?: string;
  kind?: string;
  total?: number;
  done?: number;
  failed?: number;
  started_at?: string;
  finished_at?: string | null;
  last_error?: string | null;
}

export interface ToolLink {
  tool_id: string;
  name: string;
  category: string;
  category_label: string;
  url: string;
  cost: "free" | "freemium" | "paid";
  account: boolean;
  note: string | null;
}

export interface ToolCatalog {
  categories: { id: string; label: string; count: number }[];
  sources: { id: string; label: string; count: number }[];
  tools: {
    id: string;
    name: string;
    category: string;
    category_label: string;
    url: string;
    cost: "free" | "freemium" | "paid";
    account: boolean;
    note?: string;
    kinds: string[];
    via: string[];
  }[];
}

export interface DorkRecipe {
  label: string;
  query: string;
  engines: { id: string; name: string; url: string }[];
}

export const KIND_LABELS: Record<SelectorKind, string> = {
  domain: "Alan adı",
  ip: "IP",
  url: "URL",
  email: "E-posta",
  md5: "MD5",
  sha1: "SHA-1",
  sha256: "SHA-256",
  cve: "CVE",
  attack: "ATT&CK",
  asn: "ASN",
  btc: "Bitcoin",
  eth: "Ethereum",
  coord: "Koordinat",
};

export function selectorHref(id: string): string {
  return `/selectors/view?id=${encodeURIComponent(id)}`;
}

export interface SearchResult {
  query: string;
  detected: { id: string; kind: SelectorKind; value: string; label: string; exists: boolean } | null;
  groups: {
    key: string;
    label: string;
    total: number;
    items: { id: string; title: string; subtitle: string | null; href: string; kind?: SelectorKind }[];
  }[];
}

export interface SunPosition {
  azimuth: number;
  elevation: number;
}

export interface SunShadow {
  direction: number;
  length_ratio: number;
}

export interface SunResult {
  lat: number;
  lon: number;
  at_utc: string;
  position: SunPosition;
  shadow: SunShadow | null;
  day: {
    date: string;
    sunrise_utc: string | null;
    sunset_utc: string | null;
    solar_noon_utc: string | null;
    max_elevation: number;
    rows: ({ utc: string; shadow: SunShadow | null } & SunPosition)[];
  };
}

export interface ChronoWindow {
  from_utc: string;
  to_utc: string;
  best_utc: string;
  error: number;
  sun: SunPosition;
  shadow: SunShadow;
}
