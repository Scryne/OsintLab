"use client";

import { useEffect, useMemo, useState } from "react";
import { FileSearch, Layers, Loader2, Plus, RefreshCw, Square } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { KIND_LABELS, type ExtractedSelector, type SelectorKind } from "@/lib/types-pivot";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { EmptyState, ErrorState } from "@/components/ui/state";
import { SkeletonRows } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { SelectorChip } from "@/components/pivot/selector-chip";
import { QuickPivot } from "@/components/pivot/quick-pivot";
import { cn } from "@/lib/utils";

const PAGE = 100;
const SORT_LABELS: Record<string, string> = { sightings: "En çok görülen", recent: "En son görülen", value: "Değere göre" };

function day(iso: string | null): string {
  return iso ? new Date(iso).toLocaleDateString("tr-TR", { day: "2-digit", month: "short", year: "numeric" }) : "—";
}

/** Faz 29 — Seçici İndeksi.
 *
 * Entity katmanı "kim, ne" sorusunu taşıyordu; bu sayfa profesyonel OSINT'in pivot noktalarını
 * taşıyor: alan adı, IP, hash, CVE, ATT&CK tekniği... Hepsi toplanan metinden deterministik olarak
 * çıkarılıyor ve her biri nerede görüldüğüne bağlı. Ölçüm (2026-10-24): 4.408 gözlemde 386 farklı
 * CVE vardı ve sistem hiçbirini tanımıyordu. */
export default function SelectorsPage() {
  const toast = useToast();
  const [kind, setKind] = useState<SelectorKind | "">("");
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState("sightings");
  const [ignored, setIgnored] = useState(false);
  const [kevOnly, setKevOnly] = useState(false);
  const [limit, setLimit] = useState(PAGE);

  useEffect(() => {
    const t = setTimeout(() => setQuery(q.trim()), 250);
    return () => clearTimeout(t);
  }, [q]);

  const { data: kinds, reload: reloadKinds } = useApi(() => api.selectors.kinds(), []);
  const { data, error, loading, refreshing, reload } = useApi(
    () => api.selectors.list({ kind: kind || undefined, q: query || undefined, sort, limit, include_ignored: ignored, flag: kevOnly ? "kev" : undefined }),
    [kind, query, sort, limit, ignored, kevOnly]
  );
  const total = useMemo(() => (kinds ?? []).reduce((a, k) => a + k.count, 0), [kinds]);

  async function reindex() {
    try {
      const r = await api.selectors.reindex();
      toast(`${r.observations_scanned} gözlem ve ${r.evidence_scanned} belge tarandı · ${r.new_sightings} yeni geçiş · ${r.duration_seconds} sn`, "success");
      reload();
      reloadKinds();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Tarama başarısız", "error");
    }
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="font-display text-[2rem] font-semibold tracking-tight text-balance text-foreground">Seçiciler</h1>
          <p className="max-w-2xl text-sm leading-relaxed text-pretty text-text-secondary">
            Toplanan metinlerdeki makine-okunur göstergeler — alan adı, IP, hash, CVE, ATT&amp;CK tekniği, kripto adresi.
            Her biri nerede görüldüğüne bağlı; birinden ötekine kaynağıyla birlikte geçebilirsin. Kişi seçicisi (kullanıcı
            adı, telefon) bilinçli olarak yok.
          </p>
        </div>
        <Button size="sm" variant="outline" onClick={reindex} title="Bütün gözlem ve belgeleri yeniden tara">
          <RefreshCw aria-hidden className="h-3.5 w-3.5" />
          Yeniden tara
        </Button>
      </header>

      <QuickPivot />
      <ExtractPanel onAdded={() => { reload(); reloadKinds(); }} />

      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Seçici türü">
          <KindButton active={kind === ""} onClick={() => { setKind(""); setLimit(PAGE); }} label="Hepsi" count={total} />
          {(kinds ?? []).filter((k) => k.count > 0).map((k) => (
            <KindButton key={k.kind} active={kind === k.kind} onClick={() => { setKind(k.kind); setLimit(PAGE); }} label={KIND_LABELS[k.kind]} count={k.count} />
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Değerde ara…" aria-label="Seçici değerinde ara" className="max-w-xs" />
          <Select value={sort} onValueChange={(v) => v && setSort(v)}>
            <SelectTrigger aria-label="Sıralama" className="w-44">
              <SelectValue>{(v: string) => SORT_LABELS[v] ?? v}</SelectValue>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="sightings">En çok görülen</SelectItem>
              <SelectItem value="recent">En son görülen</SelectItem>
              <SelectItem value="value">Değere göre</SelectItem>
            </SelectContent>
          </Select>
          <label className="flex items-center gap-2 text-sm text-text-secondary">
            <Checkbox checked={kevOnly} onCheckedChange={(v) => { setKevOnly(!!v); setLimit(PAGE); }} aria-label="Yalnız gerçekte sömürülenler (KEV)" />
            Yalnız sömürülenler (KEV)
          </label>
          <label className="flex items-center gap-2 text-sm text-text-secondary">
            <Checkbox checked={ignored} onCheckedChange={(v) => setIgnored(!!v)} aria-label="Yok sayılanları da göster" />
            Yok sayılanları da göster
          </label>
          {refreshing && <Loader2 aria-label="Yükleniyor" className="h-4 w-4 animate-spin text-text-tertiary" />}
        </div>
        {kind && <BulkEnrich kind={kind} onFinished={() => { reload(); }} />}
      </div>

      {loading && <SkeletonRows count={8} />}
      {error && <ErrorState error={error} onRetry={reload} />}
      {data && data.items.length === 0 && (
        <EmptyState
          title={query || kind ? "Bu filtreyle seçici yok" : "Henüz seçici yok"}
          description={query || kind ? "Filtreyi kaldır ya da başka bir değer ara." : "Toplayıcılardan içerik geldikçe seçiciler kendiliğinden çıkarılır; elle eklemek için yukarıya bir değer yapıştır."}
        />
      )}
      {data && data.items.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full text-left text-sm">
            <thead className="bg-white/[0.03] text-xs text-text-tertiary">
              <tr>
                <th className="px-3 py-2 font-medium">Seçici</th>
                <th className="px-3 py-2 text-right font-medium">Gözlem</th>
                <th className="px-3 py-2 text-right font-medium">Belge</th>
                <th className="px-3 py-2 text-right font-medium">Zenginleştirme</th>
                <th className="px-3 py-2 font-medium">Son görülme</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((s) => (
                <tr key={s.id} className="border-t border-border">
                  <td className="max-w-[28rem] px-3 py-1.5">
                    <SelectorChip id={s.id} kind={s.kind} value={s.value} ignored={s.status === "IGNORED"} />
                    {s.flags?.includes("KEV") && (
                      <span className="ml-2 rounded border border-priority-high/40 px-1 py-0.5 font-mono text-[10px] text-priority-high-text" title="CISA KEV: gerçekte sömürülüyor">
                        KEV
                      </span>
                    )}
                    {s.origin !== "extracted" && (
                      <span className="ml-2 text-[10px] text-text-tertiary">{s.origin === "manual" ? "elle" : "zenginleştirmeden"}</span>
                    )}
                  </td>
                  <td className="px-3 py-1.5 text-right font-mono text-xs tabular-nums">{s.observation_count || "—"}</td>
                  <td className="px-3 py-1.5 text-right font-mono text-xs tabular-nums">{s.evidence_count || "—"}</td>
                  <td className="px-3 py-1.5 text-right font-mono text-xs tabular-nums">{s.enrichment_count || "—"}</td>
                  <td className="px-3 py-1.5 font-mono text-xs text-text-secondary">{day(s.last_seen)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {data && data.total > data.items.length && (
        <Button variant="outline" className="self-center" onClick={() => setLimit((l) => l + PAGE)}>
          Daha fazla göster ({data.total - data.items.length} kaldı)
        </Button>
      )}
    </div>
  );
}

function KindButton({ active, onClick, label, count }: { active: boolean; onClick: () => void; label: string; count: number }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
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

function ExtractPanel({ onAdded }: { onAdded: () => void }) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [found, setFound] = useState<ExtractedSelector[] | null>(null);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);

  async function run() {
    setBusy(true);
    try {
      const res = await api.selectors.extract(text);
      setFound(res);
      setPicked(new Set(res.map((r) => r.id)));
    } catch (err) {
      toast(err instanceof Error ? err.message : "Çıkarılamadı", "error");
    } finally {
      setBusy(false);
    }
  }

  async function add() {
    const items = (found ?? []).filter((f) => picked.has(f.id));
    setBusy(true);
    let ok = 0;
    for (const f of items) {
      try {
        await api.selectors.create(f.value, "metinden elle çıkarıldı");
        ok += 1;
      } catch {
        // Tek bir değer reddedilirse diğerleri yine eklensin.
      }
    }
    setBusy(false);
    toast(`${ok} seçici eklendi`, "success");
    onAdded();
  }

  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} className="flex items-center gap-2 self-start text-sm text-text-secondary hover:text-foreground">
        <FileSearch aria-hidden className="h-4 w-4" />
        Bir metinden seçici çıkar (rapor, advisory, e-posta başlığı…)
      </button>
    );
  }
  return (
    <div className="flex flex-col gap-2 rounded-xl border border-border bg-surface p-3">
      <label htmlFor="extract-text" className="text-sm font-medium text-foreground">Metinden çıkar</label>
      <Textarea id="extract-text" rows={6} value={text} onChange={(e) => setText(e.target.value)} placeholder="Metni yapıştır — grafa yazılmaz, önce neyin bulunduğunu görürsün." className="font-mono text-xs" />
      <div className="flex gap-2">
        <Button size="sm" onClick={run} disabled={!text.trim() || busy}>Çıkar</Button>
        <Button size="sm" variant="ghost" onClick={() => { setOpen(false); setFound(null); setText(""); }}>Kapat</Button>
      </div>
      {found && found.length === 0 && <p className="text-sm text-text-tertiary">Metinde seçici bulunamadı.</p>}
      {found && found.length > 0 && (
        <div className="flex flex-col gap-2">
          <ul className="flex max-h-72 flex-col gap-1 overflow-y-auto">
            {found.map((f) => (
              <li key={f.id} className="flex items-start gap-2 rounded-md border border-border px-2 py-1.5">
                <Checkbox
                  checked={picked.has(f.id)}
                  onCheckedChange={(v) => setPicked((p) => { const n = new Set(p); if (v) n.add(f.id); else n.delete(f.id); return n; })}
                  aria-label={`${f.value} seç`}
                />
                <div className="min-w-0">
                  <SelectorChip id={f.id} kind={f.kind} value={f.value} link={false} />
                  {f.defanged && <span className="ml-2 text-[10px] text-text-tertiary">defang&apos;li yazılmış</span>}
                  <p className="mt-0.5 truncate font-mono text-[11px] text-text-tertiary">{f.context}</p>
                </div>
              </li>
            ))}
          </ul>
          <Button size="sm" className="self-start" onClick={add} disabled={!picked.size || busy}>
            <Plus aria-hidden className="h-3.5 w-3.5" />
            Seçili {picked.size} değeri ekle
          </Button>
        </div>
      )}
    </div>
  );
}

function BulkEnrich({ kind, onFinished }: { kind: SelectorKind; onFinished: () => void }) {
  const toast = useToast();
  const { data: modules } = useApi(() => api.enrichment.modules(), []);
  const [polling, setPolling] = useState(false);
  const { data: job, reload } = useApi(
    async () => {
      const j = await api.enrichment.bulkStatus();
      setPolling((was) => {
        if (was && !j.running) onFinished();
        return j.running;
      });
      return j;
    },
    [],
    { pollMs: polling ? 2000 : undefined }
  );
  const options = (modules ?? []).filter((m) => m.target === "selector" && m.kinds.includes(kind) && m.opsec !== "ACTIVE" && m.enabled);
  const [module, setModule] = useState<string>("");
  const chosen = options.find((m) => m.name === module) ?? options[0];

  if (!options.length) return null;

  async function start() {
    if (!chosen) return;
    try {
      await api.enrichment.bulk(chosen.name, kind);
      setPolling(true);
      reload();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Başlatılamadı", "error");
    }
  }

  const running = job?.running;
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2 text-sm">
      <Layers aria-hidden className="h-4 w-4 text-text-tertiary" />
      <span className="text-text-secondary">Bu türün hepsine uygula:</span>
      <Select value={chosen?.name ?? ""} onValueChange={(v) => v && setModule(v)}>
        <SelectTrigger aria-label="Toplu modül" className="h-8 w-56">
          <SelectValue>{(v: string) => options.find((m) => m.name === v)?.label ?? v}</SelectValue>
        </SelectTrigger>
        <SelectContent>
          {options.map((m) => (
            <SelectItem key={m.name} value={m.name}>
              {m.label} · {m.opsec === "LOCAL" ? "yerel" : "pasif"}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {running ? (
        <>
          <span className="font-mono text-xs tabular-nums text-text-secondary">
            {job?.module} · {job?.done}/{job?.total}
            {job?.failed ? ` · ${job.failed} hata` : ""}
          </span>
          <Button size="sm" variant="ghost" onClick={async () => { await api.enrichment.cancelBulk(); reload(); }}>
            <Square aria-hidden className="h-3.5 w-3.5" /> Durdur
          </Button>
        </>
      ) : (
        <Button size="sm" variant="outline" onClick={start}>
          Yalnız eksiklere uygula
        </Button>
      )}
      {!running && job?.finished_at && (
        <span className="text-xs text-text-tertiary">
          Son toplu iş: {job.module} · {job.done}/{job.total}
          {job.failed ? ` · ${job.failed} hata (${job.last_error ?? ""})` : ""}
        </span>
      )}
    </div>
  );
}
