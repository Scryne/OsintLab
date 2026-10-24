"use client";

import { Suspense, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowLeft, Check, Copy, Eye, EyeOff, FileText, Link2, Network, Unlink } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import type { SelectorDetail, SelectorPivot } from "@/lib/types-pivot";
import { Button } from "@/components/ui/button";
import { ConfirmButton } from "@/components/ui/confirm-button";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EmptyState, ErrorState } from "@/components/ui/state";
import { SkeletonDetail, SkeletonRows } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { SearchablePicker } from "@/components/forms/searchable-picker";
import { EnrichmentPanel } from "@/components/pivot/enrichment-panel";
import { KIND_ICON, SelectorChip } from "@/components/pivot/selector-chip";
import { PivotGraphView } from "@/components/pivot/pivot-graph";
import { DorkList, ToolLinks } from "@/components/pivot/tool-links";

// Pivot ilişkilerinin okunur adı. Yön önemli: "resolves_to" giden kenarda "çözüldüğü IP",
// gelen kenarda "buna çözülen alan adı".
const RELATION: Record<string, { out: string; in: string }> = {
  resolves_to: { out: "Çözüldüğü IP'ler", in: "Bu IP'ye çözülen alan adları" },
  alias_of: { out: "CNAME hedefi", in: "Buna CNAME veren adlar" },
  mail_via: { out: "E-posta sunucuları (MX)", in: "Bunu MX olarak kullanan alan adları" },
  nameserver: { out: "Ad sunucuları", in: "Bu ad sunucusunu kullanan alan adları" },
  spf_include: { out: "SPF ile yetkilendirilen", in: "Bunu SPF'ine ekleyen alan adları" },
  spf_allows: { out: "SPF'in izin verdiği IP'ler", in: "SPF'inde bu IP'ye izin verenler" },
  ptr: { out: "Ters DNS adı", in: "Ters DNS'i bu ada çıkan IP'ler" },
  subdomain_of: { out: "Üst alan adı", in: "Alt alan adları (sertifika şeffaflığı)" },
  hostname: { out: "Ana makine adları (Shodan)", in: "Bu adı taşıyan IP'ler" },
  exposes: { out: "Bilinen açıklar (Shodan)", in: "Bu açığı taşıyan IP'ler" },
  announced_by: { out: "Duyuran ASN", in: "Bu ASN'nin duyurduğu IP'ler" },
  scanned_on: { out: "urlscan'de görüldüğü IP'ler", in: "urlscan'de bu IP'de görülen" },
  links_to: { out: "Bağlantı verdiği host'lar", in: "Buna bağlantı veren siteler" },
};

function relLabel(p: SelectorPivot): string {
  const r = RELATION[p.relation];
  return r ? (p.direction === "out" ? r.out : r.in) : `${p.relation} (${p.direction === "out" ? "→" : "←"})`;
}

export default function SelectorViewPage() {
  return (
    <Suspense fallback={<div className="mx-auto max-w-5xl"><SkeletonDetail /></div>}>
      <SelectorView />
    </Suspense>
  );
}

function SelectorView() {
  const params = useSearchParams();
  const id = params.get("id") ?? "";
  const { data, error, loading, reload } = useApi(() => api.selectors.detail(id), [id]);

  if (!id) return <EmptyState title="Seçici belirtilmedi" description="Seçiciler listesinden birini aç." />;
  if (loading) return <div className="mx-auto max-w-5xl"><SkeletonDetail /></div>;
  if (error) return <div className="mx-auto max-w-5xl"><ErrorState error={error} onRetry={reload} /></div>;
  if (!data) return null;
  return <Detail data={data} reload={reload} />;
}

function Detail({ data, reload }: { data: SelectorDetail; reload: () => void }) {
  const toast = useToast();
  const sel = data.selector;
  const Icon = KIND_ICON[sel.kind];
  const [copied, setCopied] = useState(false);
  const [graphKey, setGraphKey] = useState(0);

  const pivotGroups = useMemo(() => {
    const m = new Map<string, SelectorPivot[]>();
    for (const p of data.pivots) {
      const k = relLabel(p);
      m.set(k, [...(m.get(k) ?? []), p]);
    }
    return [...m.entries()];
  }, [data.pivots]);

  async function copy() {
    try {
      await navigator.clipboard.writeText(sel.value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Pano izni yoksa değer ekranda seçilebilir.
    }
  }

  async function toggleIgnore() {
    try {
      await api.selectors.update(sel.id, { status: sel.status === "IGNORED" ? "ACTIVE" : "IGNORED" });
      toast(sel.status === "IGNORED" ? "Seçici geri alındı" : "Yanlış pozitif olarak işaretlendi — listede gizlenir, silinmez", "default");
      reload();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Güncellenemedi", "error");
    }
  }

  function refreshAll() {
    reload();
    setGraphKey((k) => k + 1);
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <Link href="/selectors" className="inline-flex items-center gap-1 self-start text-sm text-text-secondary hover:text-foreground">
        <ArrowLeft aria-hidden className="h-4 w-4" /> Seçiciler
      </Link>

      <header className="flex flex-col gap-3">
        <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-text-tertiary">
          <Icon aria-hidden className="h-4 w-4" />
          {data.label}
          {sel.status === "IGNORED" && <span className="rounded-full border border-border px-1.5 py-0.5 normal-case">yok sayıldı</span>}
          <span className="normal-case tracking-normal">· {sel.origin === "extracted" ? "metinden çıkarıldı" : sel.origin === "manual" ? "elle eklendi" : "zenginleştirmeden geldi"}</span>
        </div>
        <div className="flex flex-wrap items-start gap-2">
          <h1 className="min-w-0 break-all font-mono text-xl font-medium text-foreground sm:text-2xl">{sel.value}</h1>
          <button type="button" onClick={copy} aria-label="Değeri kopyala" className="mt-1 rounded p-1 text-text-tertiary hover:bg-white/5 hover:text-foreground">
            {copied ? <Check aria-hidden className="h-4 w-4" /> : <Copy aria-hidden className="h-4 w-4" />}
          </button>
        </div>
        <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-sm text-text-secondary">
          <span><strong className="tabular-nums text-foreground">{data.observation_count}</strong> gözlemde</span>
          <span><strong className="tabular-nums text-foreground">{data.source_hosts.length}</strong> farklı kaynakta</span>
          <span><strong className="tabular-nums text-foreground">{data.pivots.length}</strong> pivot</span>
          {data.documents.length > 0 && <span><strong className="tabular-nums text-foreground">{data.documents.length}</strong> belgede</span>}
          <Button size="sm" variant="ghost" onClick={toggleIgnore} className="ml-auto">
            {sel.status === "IGNORED" ? <Eye aria-hidden className="h-3.5 w-3.5" /> : <EyeOff aria-hidden className="h-3.5 w-3.5" />}
            {sel.status === "IGNORED" ? "Geri al" : "Yanlış pozitif"}
          </Button>
        </div>
        <NoteEditor id={sel.id} note={sel.note ?? ""} onSaved={reload} />
      </header>

      <Tabs defaultValue="enrich">
        <div className="-mx-1 overflow-x-auto px-1">
          <TabsList className="w-max">
            <TabsTrigger value="enrich">Zenginleştirme</TabsTrigger>
            <TabsTrigger value="pivots">Pivotlar ({data.pivots.length})</TabsTrigger>
            <TabsTrigger value="seen">Görüldüğü yerler ({data.observation_count + data.documents.length})</TabsTrigger>
            <TabsTrigger value="tools">Dış araçlar</TabsTrigger>
            <TabsTrigger value="links">Entity bağları ({data.entities.length})</TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="enrich" className="pt-2">
          <EnrichmentPanel targetId={sel.id} onPivotsChanged={refreshAll} />
        </TabsContent>

        <TabsContent value="pivots" className="flex flex-col gap-5 pt-2">
          <PivotGraphView key={graphKey} selectorId={sel.id} />
          {pivotGroups.map(([label, items]) => (
            <section key={label} className="flex flex-col gap-1.5">
              <h3 className="text-[11px] font-medium uppercase tracking-wide text-text-tertiary">
                {label} <span className="tabular-nums">({items.length})</span>
              </h3>
              <div className="flex flex-wrap gap-1.5">
                {items.map((p) => (
                  <SelectorChip key={`${p.id}-${p.relation}-${p.direction}`} id={p.id} kind={p.kind} value={p.value} />
                ))}
              </div>
            </section>
          ))}
          {data.co_occurring.length > 0 && (
            <section className="flex flex-col gap-1.5">
              <h3 className="text-[11px] font-medium uppercase tracking-wide text-text-tertiary">Aynı metinlerde birlikte geçenler</h3>
              <div className="flex flex-wrap gap-1.5">
                {data.co_occurring.map((c) => (
                  <span key={c.id} className="inline-flex items-center gap-1">
                    <SelectorChip id={c.id} kind={c.kind} value={c.value} />
                    <span className="font-mono text-[10px] text-text-tertiary">×{c.shared}</span>
                  </span>
                ))}
              </div>
            </section>
          )}
        </TabsContent>

        <TabsContent value="seen" className="flex flex-col gap-3 pt-2">
          {data.source_hosts.length > 0 && (
            <p className="text-xs text-text-tertiary">Kaynaklar: <span className="font-mono">{data.source_hosts.join(" · ")}</span></p>
          )}
          {data.sightings.length === 0 && data.documents.length === 0 && (
            <EmptyState title="Toplanan metinlerde geçmiyor" description="Bu seçici elle ya da bir zenginleştirme sonucundan eklendi." />
          )}
          <ul className="flex flex-col gap-2">
            {data.documents.map((d) => (
              <li key={d.evidence_id} className="rounded-lg border border-border bg-surface p-3">
                <div className="flex items-center gap-2 text-xs text-text-secondary">
                  <FileText aria-hidden className="h-3.5 w-3.5" />
                  <Link href="/evidence" className="hover:text-foreground">Belge · {d.file_path?.split(/[\\/]/).pop()}</Link>
                </div>
                <p className="mt-1 font-mono text-xs leading-relaxed text-text-secondary">…{d.context}…</p>
              </li>
            ))}
            {data.sightings.map((s) => (
              <li key={s.observation_id} className="rounded-lg border border-border bg-surface p-3">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-text-tertiary">
                  <span className="font-mono">{s.observed_at ? new Date(s.observed_at).toLocaleString("tr-TR") : "—"}</span>
                  {s.source_url && (
                    <a href={s.source_url} target="_blank" rel="noopener noreferrer nofollow" className="truncate font-mono hover:text-foreground">
                      {(() => { try { return new URL(s.source_url).hostname; } catch { return s.source_url; } })()}
                    </a>
                  )}
                  {s.defanged && <span>defang&apos;li yazılmış</span>}
                  {(s.occurrences ?? 1) > 1 && <span>{s.occurrences} kez</span>}
                  <Link href={`/observations?ids=${s.observation_id}`} className="hover:text-foreground">gözlem</Link>
                  {s.claim_id && <span className="text-text-secondary">claim&apos;e dönüştü · {s.claim_state}</span>}
                </div>
                {/* Toplanan metin güvenilmeyen veridir (Q22) — yalnızca gösterilir, yorumlanmaz. */}
                <p className="mt-1 font-mono text-xs leading-relaxed text-text-secondary">…{s.context}…</p>
              </li>
            ))}
          </ul>
          {data.observation_count > data.sightings.length && (
            <p className="text-xs text-text-tertiary">İlk {data.sightings.length} geçiş gösteriliyor.</p>
          )}
        </TabsContent>

        <TabsContent value="tools" className="flex flex-col gap-6 pt-2">
          <ToolLinks kind={sel.kind} value={sel.value} />
          <section className="flex flex-col gap-2">
            <h3 className="text-sm font-medium text-foreground">Arama operatörleri</h3>
            <DorkList kind={sel.kind} value={sel.value} />
          </section>
        </TabsContent>

        <TabsContent value="links" className="pt-2">
          <EntityLinks data={data} onChanged={reload} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function NoteEditor({ id, note, onSaved }: { id: string; note: string; onSaved: () => void }) {
  const toast = useToast();
  const [value, setValue] = useState(note);
  const [editing, setEditing] = useState(false);
  if (!editing) {
    return (
      <button type="button" onClick={() => setEditing(true)} className="self-start text-left text-sm text-text-secondary hover:text-foreground">
        {note ? <span className="border-l-2 border-brand-accent pl-2">{note}</span> : <span className="text-text-tertiary">+ Not ekle (senin yorumun)</span>}
      </button>
    );
  }
  return (
    <div className="flex flex-col gap-2">
      <Textarea value={value} onChange={(e) => setValue(e.target.value)} rows={3} aria-label="Seçici notu" />
      <div className="flex gap-2">
        <Button
          size="sm"
          onClick={async () => {
            try {
              await api.selectors.update(id, { note: value });
              setEditing(false);
              onSaved();
            } catch (err) {
              toast(err instanceof Error ? err.message : "Kaydedilemedi", "error");
            }
          }}
        >
          Notu kaydet
        </Button>
        <Button size="sm" variant="ghost" onClick={() => { setValue(note); setEditing(false); }}>Vazgeç</Button>
      </div>
    </div>
  );
}

function EntityLinks({ data, onChanged }: { data: SelectorDetail; onChanged: () => void }) {
  const toast = useToast();
  const { data: entities, loading } = useApi(() => api.entities.list(), []);
  const [target, setTarget] = useState<string | null>(null);
  const linked = new Set(data.entities.map((e) => e.id));
  const items = (entities ?? []).filter((e) => !linked.has(e.id)).map((e) => ({ id: e.id, label: e.name, sublabel: e.entity_type }));

  async function link() {
    if (!target) return;
    try {
      await api.selectors.linkEntity(data.selector.id, target);
      setTarget(null);
      toast("Bağlandı", "success");
      onChanged();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Bağlanamadı", "error");
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-pretty text-text-secondary">
        Bir seçiciyi bir entity&apos;ye bağlamak bir iddiadır: &quot;bu altyapı/gösterge şu kuruma ait&quot;. Sistem bunu kendisi
        kurmaz; zenginleştirme sonuçları yalnızca aday gösterir.
      </p>
      {data.entities.length > 0 && (
        <ul className="flex flex-col gap-1.5">
          {data.entities.map((e) => (
            <li key={e.id} className="flex items-center justify-between gap-2 rounded-md border border-border bg-surface px-3 py-2">
              <Link href={`/entities/${e.id}`} className="flex items-center gap-2 text-sm text-foreground hover:underline">
                <Network aria-hidden className="h-3.5 w-3.5 text-text-tertiary" />
                {e.name}
                <span className="text-xs text-text-tertiary">{e.entity_type}</span>
              </Link>
              <ConfirmButton
                variant="ghost"
                onConfirm={async () => {
                  await api.selectors.unlinkEntity(data.selector.id, e.id);
                  onChanged();
                }}
                confirmAction="Bağı kaldır"
                aria-label={`${e.name} bağını kaldır`}
              >
                <Unlink aria-hidden className="h-3.5 w-3.5" />
              </ConfirmButton>
            </li>
          ))}
        </ul>
      )}
      {loading ? (
        <SkeletonRows count={2} />
      ) : (
        <div className="flex flex-col gap-2">
          <SearchablePicker items={items} value={target} onChange={setTarget} placeholder="Entity ara…" aria-label="Bağlanacak entity" />
          <Button size="sm" className="self-start" onClick={link} disabled={!target}>
            <Link2 aria-hidden className="h-3.5 w-3.5" />
            Entity&apos;ye bağla
          </Button>
        </div>
      )}
    </div>
  );
}
