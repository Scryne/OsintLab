"use client";

import { Suspense, useMemo, useState } from "react";
import { ExternalLink, Lock, Search } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { ErrorState } from "@/components/ui/state";
import { SkeletonRows } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { SunTool } from "@/components/pivot/sun-tool";
import { Button } from "@/components/ui/button";

const COST = { free: "ücretsiz", freemium: "kısmen ücretsiz", paid: "ücretli" } as const;
const PAGE_SIZE = 60;

/** Faz 32 — Araç Rehberi. Kaynak: @osintnewsletter, @0xtechrock, @techniquesOsint'in paylaştıkları ve
 * Scryne'ın derlemesi (2026-10-24 taraması, `app/toolcatalog.py`). Q25 sınırı katalog için kaldırıldı;
 * kişi ve kimlik araçları kendi kategorilerinde. 700+ satır olduğu için liste parça parça çizilir. */
export default function ToolsPage() {
  const { data, error, loading, reload } = useApi(() => api.tools.catalog(), []);
  const [category, setCategory] = useState("");
  const [source, setSource] = useState("");
  const [q, setQ] = useState("");
  const [limit, setLimit] = useState(PAGE_SIZE);
  const sourceLabel = useMemo(() => new Map((data?.sources ?? []).map((s) => [s.id, s.label])), [data]);

  const tools = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return (data?.tools ?? []).filter(
      (t) =>
        (!category || t.category === category) &&
        (!source || (t.via ?? []).includes(source)) &&
        (!needle || t.name.toLowerCase().includes(needle) || (t.note ?? "").toLowerCase().includes(needle))
    );
  }, [data, category, source, q]);
  const visible = tools.slice(0, limit);

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-8">
      <header>
        <h1 className="font-display text-[2rem] font-semibold tracking-tight text-balance text-foreground">Araç Rehberi</h1>
        <p className="max-w-2xl text-sm leading-relaxed text-pretty text-text-secondary">
          Kürasyonlu dış OSINT araçları. Bir seçicinin sayfasında bu araçlar o değerle hazır bağlantı olarak açılır. OsintLab bu
          servislere istek atmaz — bağlantı tarayıcında açılır, hangi hesapla ve hangi ağdan açılacağı senin kararın.
        </p>
      </header>

      <DorkBuilder />
      <Suspense fallback={null}>
        <SunTool />
      </Suspense>

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-medium uppercase tracking-wide text-text-tertiary">Katalog</h2>
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Kategori">
          <Chip active={!category} onClick={() => { setCategory(""); setLimit(PAGE_SIZE); }} label="Hepsi" count={data?.tools.length ?? 0} />
          {data?.categories.map((c) => (
            <Chip key={c.id} active={category === c.id} onClick={() => { setCategory(c.id); setLimit(PAGE_SIZE); }} label={c.label} count={c.count} />
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Paylaşan kaynak">
          <span className="mr-1 text-xs text-text-tertiary">Paylaşan</span>
          <Chip active={!source} onClick={() => { setSource(""); setLimit(PAGE_SIZE); }} label="Hepsi" count={data?.tools.length ?? 0} />
          {data?.sources?.map((s) => (
            <Chip key={s.id} active={source === s.id} onClick={() => { setSource(s.id); setLimit(PAGE_SIZE); }} label={s.label} count={s.count} />
          ))}
        </div>
        <Input
          value={q}
          onChange={(e) => { setQ(e.target.value); setLimit(PAGE_SIZE); }}
          placeholder="Araç ara…"
          aria-label="Araç ara"
          className="max-w-xs"
        />
        {data && <p className="text-xs text-text-tertiary" aria-live="polite">{tools.length} araç</p>}
        {loading && <SkeletonRows count={6} />}
        {error && <ErrorState error={error} onRetry={reload} />}
        <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {visible.map((t) => (
            <li key={t.id}>
              <a
                href={t.url}
                target="_blank"
                rel="noopener noreferrer nofollow"
                className="group flex h-full flex-col gap-1 rounded-lg border border-border bg-surface p-3 transition-colors hover:border-white/25 hover:bg-white/[0.07]"
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="flex items-center gap-1.5 text-sm font-medium text-foreground">
                    {t.name}
                    {t.account && <Lock aria-label="hesap gerekir" className="h-3 w-3 text-text-tertiary" />}
                  </span>
                  <ExternalLink aria-hidden className="h-3.5 w-3.5 text-text-tertiary group-hover:text-foreground" />
                </span>
                <span className="text-[11px] text-text-tertiary">
                  {t.category_label} · {COST[t.cost]}
                  {t.kinds.length > 0 && ` · ${t.kinds.length} türle bağlantılı`}
                </span>
                {t.note && <span className="text-xs text-pretty text-text-secondary">{t.note}</span>}
                {(t.via?.length ?? 0) > 0 && (
                  <span className="mt-auto pt-1 text-[11px] text-text-tertiary">
                    Paylaşan: {(t.via ?? []).map((v) => sourceLabel.get(v) ?? v).join(", ")}
                  </span>
                )}
              </a>
            </li>
          ))}
        </ul>
        {tools.length > visible.length && (
          <Button variant="outline" className="self-start" onClick={() => setLimit((n) => n + PAGE_SIZE)}>
            Daha fazla göster ({tools.length - visible.length} kaldı)
          </Button>
        )}
      </section>
    </div>
  );
}

function Chip({ active, onClick, label, count }: { active: boolean; onClick: () => void; label: string; count: number }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors",
        active ? "border-white/80 bg-white/95 text-neutral-900" : "border-border text-text-secondary hover:border-white/25 hover:text-foreground"
      )}
    >
      {label}
      <span className={cn("font-mono tabular-nums", active ? "text-neutral-600" : "text-text-tertiary")}>{count}</span>
    </button>
  );
}

const ENGINES = [
  { name: "Google", url: "https://www.google.com/search?q=" },
  { name: "Bing", url: "https://www.bing.com/search?q=" },
  { name: "DuckDuckGo", url: "https://duckduckgo.com/?q=" },
  { name: "Yandex", url: "https://yandex.com/search/?text=" },
];

/** Arama operatörü kurucu. Operatörler motorlar arasında aynı değil: `filetype:` Google/Bing'de
 * çalışır, Yandex'te `mime:`; burada ortak alt küme kullanılıyor ve sorgu açıkça gösteriliyor ki
 * kullanıcı motoruna göre düzeltebilsin. */
function DorkBuilder() {
  const [terms, setTerms] = useState("");
  const [exact, setExact] = useState("");
  const [site, setSite] = useState("");
  const [excludeSite, setExcludeSite] = useState("");
  const [filetype, setFiletype] = useState("");
  const [inurl, setInurl] = useState("");
  const [intitle, setIntitle] = useState("");
  const [exclude, setExclude] = useState("");
  const [after, setAfter] = useState("");

  const query = useMemo(() => {
    const parts: string[] = [];
    if (terms.trim()) parts.push(terms.trim());
    if (exact.trim()) parts.push(`"${exact.trim().replace(/"/g, "")}"`);
    for (const s of site.split(/[,\s]+/).filter(Boolean)) parts.push(`site:${s}`);
    for (const s of excludeSite.split(/[,\s]+/).filter(Boolean)) parts.push(`-site:${s}`);
    const types = filetype.split(/[,\s]+/).filter(Boolean);
    if (types.length === 1) parts.push(`filetype:${types[0]}`);
    if (types.length > 1) parts.push(`(${types.map((t) => `filetype:${t}`).join(" OR ")})`);
    if (inurl.trim()) parts.push(`inurl:${inurl.trim()}`);
    if (intitle.trim()) parts.push(`intitle:"${intitle.trim().replace(/"/g, "")}"`);
    for (const w of exclude.split(/[,\s]+/).filter(Boolean)) parts.push(`-${w}`);
    if (after) parts.push(`after:${after}`);
    return parts.join(" ");
  }, [terms, exact, site, excludeSite, filetype, inurl, intitle, exclude, after]);

  const field = (id: string, label: string, value: string, set: (v: string) => void, placeholder: string, type = "text") => (
    <div className="flex flex-col gap-1">
      <Label htmlFor={id} className="text-xs text-text-secondary">{label}</Label>
      <Input id={id} type={type} value={value} onChange={(e) => set(e.target.value)} placeholder={placeholder} className="h-8 text-xs" />
    </div>
  );

  return (
    <section className="flex flex-col gap-3 rounded-xl border border-border bg-surface p-4">
      <h2 className="flex items-center gap-2 text-sm font-medium text-foreground">
        <Search aria-hidden className="h-4 w-4 text-text-tertiary" />
        Arama operatörü kurucu
      </h2>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {field("dork-terms", "Kelimeler", terms, setTerms, "ransomware leak")}
        {field("dork-exact", "Tam ifade", exact, setExact, "Siemens AG")}
        {field("dork-site", "Yalnız bu sitelerde", site, setSite, "gov.tr, europa.eu")}
        {field("dork-xsite", "Bu siteler hariç", excludeSite, setExcludeSite, "wikipedia.org")}
        {field("dork-type", "Dosya türü", filetype, setFiletype, "pdf, xlsx")}
        {field("dork-inurl", "Adreste geçen", inurl, setInurl, "admin")}
        {field("dork-intitle", "Başlıkta geçen", intitle, setIntitle, "index of")}
        {field("dork-exclude", "Hariç kelimeler", exclude, setExclude, "job, career")}
        {field("dork-after", "Bu tarihten sonra", after, setAfter, "", "date")}
      </div>
      <div className="flex flex-col gap-1">
        <Label htmlFor="dork-query" className="text-xs text-text-secondary">Sorgu (düzenlenebilir değil — alanlardan kurulur)</Label>
        <Textarea id="dork-query" readOnly value={query} rows={2} className="font-mono text-xs" />
      </div>
      <div className="flex flex-wrap gap-2">
        {ENGINES.map((e) => (
          <a
            key={e.name}
            href={query ? `${e.url}${encodeURIComponent(query)}` : undefined}
            aria-disabled={!query}
            target="_blank"
            rel="noopener noreferrer nofollow"
            className={cn(
              "inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1 text-xs",
              query ? "text-foreground hover:border-white/25" : "pointer-events-none text-text-tertiary"
            )}
          >
            {e.name} <ExternalLink aria-hidden className="h-3 w-3" />
          </a>
        ))}
      </div>
    </section>
  );
}
