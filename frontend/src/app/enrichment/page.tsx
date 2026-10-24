"use client";

import Link from "next/link";
import { Database, Download, ExternalLink, Loader2, ShieldCheck, ShieldX } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { selectorHref, type EnrichmentModule } from "@/lib/types-pivot";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { EmptyState, ErrorState } from "@/components/ui/state";
import { SkeletonRows } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { OpsecBadge } from "@/components/pivot/opsec-badge";

function size(bytes?: number): string {
  if (!bytes) return "—";
  return bytes > 1_000_000 ? `${(bytes / 1_000_000).toFixed(1)} MB` : `${Math.round(bytes / 1000)} KB`;
}

/** Faz 30 — zenginleştirme ayarları, yerel veri setleri ve koşu geçmişi.
 *
 * Bu sayfanın varlık sebebi OPSEC: her modül bir üçüncü tarafa "şununla ilgileniyorum" der.
 * Hangisinin açık olduğu, hangi host'a gittiği ve ne zaman sorulduğu tek yerde görünmeli. */
export default function EnrichmentPage() {
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-8">
      <header>
        <h1 className="font-display text-[2rem] font-semibold tracking-tight text-balance text-foreground">Zenginleştirme</h1>
        <p className="max-w-2xl text-sm leading-relaxed text-pretty text-text-secondary">
          Seçicileri ve kurumları anahtarsız, herkese açık kaynaklarla zenginleştiren modüller. Pasif modüller üçüncü taraf bir
          veritabanına sorar, hedefe dokunmaz — ama sorgu o servise ilgini gösterir. Aktif modüller hedefin kendi sunucusuna
          istek atar ve varsayılan olarak kapalıdır. Her koşunun ham yanıtı SHA-256 ile saklanır.
        </p>
      </header>
      <Modules />
      <Datasets />
      <RecentRuns />
    </div>
  );
}

function Modules() {
  const toast = useToast();
  const { data, error, loading, reload } = useApi(() => api.enrichment.modules(), []);

  async function toggle(m: EnrichmentModule, enabled: boolean) {
    try {
      await api.enrichment.toggle(m.name, enabled);
      reload();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Değiştirilemedi", "error");
    }
  }

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-sm font-medium uppercase tracking-wide text-text-tertiary">Modüller</h2>
      {loading && <SkeletonRows count={6} />}
      {error && <ErrorState error={error} onRetry={reload} />}
      {data && (
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full text-left text-sm">
            <thead className="bg-white/[0.03] text-xs text-text-tertiary">
              <tr>
                <th className="px-3 py-2 font-medium">Açık</th>
                <th className="px-3 py-2 font-medium">Modül</th>
                <th className="px-3 py-2 font-medium">Hedef</th>
                <th className="px-3 py-2 font-medium">OPSEC</th>
                <th className="px-3 py-2 font-medium">Gittiği host</th>
              </tr>
            </thead>
            <tbody>
              {data.map((m) => (
                <tr key={m.name} className="border-t border-border align-top">
                  <td className="px-3 py-2">
                    <Checkbox checked={m.enabled} onCheckedChange={(v) => toggle(m, !!v)} aria-label={`${m.label} modülünü ${m.enabled ? "kapat" : "aç"}`} />
                  </td>
                  <td className="px-3 py-2">
                    <div className="font-medium text-foreground">{m.label}</div>
                    <div className="text-xs text-text-tertiary">{m.provider}</div>
                    <div className="mt-0.5 max-w-md text-xs text-pretty text-text-secondary">{m.description}</div>
                    {m.terms_note && <div className="mt-0.5 max-w-md text-[11px] text-priority-medium-text">{m.terms_note}</div>}
                    {m.target === "entity" && m.enabled && m.opsec !== "ACTIVE" && (
                      <button
                        type="button"
                        onClick={async () => {
                          try {
                            await api.enrichment.bulk(m.name, "entity");
                            toast(`${m.label} bütün entity'lerde arka planda çalışıyor (yalnız eksikler)`, "default");
                          } catch (err) {
                            toast(err instanceof Error ? err.message : "Başlatılamadı", "error");
                          }
                        }}
                        className="mt-1 text-[11px] text-brand-accent-text hover:underline"
                      >
                        Bütün entity&apos;lere uygula
                      </button>
                    )}
                  </td>
                  <td className="px-3 py-2 text-xs text-text-secondary">{m.target === "entity" ? "Kurum (entity)" : m.target === "claim" ? "Claim" : m.kind_labels.join(", ")}</td>
                  <td className="px-3 py-2">
                    <OpsecBadge opsec={m.opsec} title={m.opsec_note} />
                    <div className="mt-1 text-[11px] text-text-tertiary">önbellek {m.cache_hours >= 1 ? `${m.cache_hours} sa` : `${Math.round(m.cache_hours * 60)} dk`}</div>
                  </td>
                  <td className="px-3 py-2 font-mono text-[11px] text-text-secondary">
                    {m.hosts.length ? m.hosts.join(", ") : m.opsec === "LOCAL" ? "— (yerel)" : "hedefin kendisi"}
                    {m.docs_url && (
                      <a href={m.docs_url} target="_blank" rel="noopener noreferrer" className="mt-1 flex items-center gap-1 font-sans text-text-tertiary hover:text-foreground">
                        belge <ExternalLink aria-hidden className="h-3 w-3" />
                      </a>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function Datasets() {
  const toast = useToast();
  const [polling, setPolling] = useState(false);
  const { data, error, loading, reload } = useApi(
    async () => {
      const rows = await api.enrichment.datasets();
      setPolling(rows.some((r) => r.downloading));
      return rows;
    },
    [],
    { pollMs: polling ? 2000 : undefined }
  );

  async function download(name: string) {
    try {
      await api.enrichment.downloadDataset(name);
      setPolling(true);
      reload();
    } catch (err) {
      toast(err instanceof Error ? err.message : "İndirilemedi", "error");
    }
  }

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-sm font-medium uppercase tracking-wide text-text-tertiary">Yerel veri setleri</h2>
      <p className="max-w-2xl text-sm text-pretty text-text-secondary">
        Bu listeler bir kez indirilip bilgisayarında aranır: &quot;bu CVE sömürülüyor mu&quot; ya da &quot;bu kurum yaptırım listesinde
        mi&quot; sorusu hiçbir servise gönderilmez. İndirilen dosyanın hash&apos;i saklanır; bir sonuç hangi tarihli listeyle bakıldığını söyler.
      </p>
      {loading && <SkeletonRows count={3} />}
      {error && <ErrorState error={error} onRetry={reload} />}
      <ul className="grid gap-2 md:grid-cols-3">
        {data?.map((d) => (
          <li key={d.name} className="flex flex-col gap-2 rounded-xl border border-border bg-surface p-3">
            <div className="flex items-center gap-2 text-sm font-medium text-foreground">
              <Database aria-hidden className="h-4 w-4 text-text-tertiary" />
              {d.label}
            </div>
            <div className="text-xs text-text-tertiary">{d.provider} · {d.license}</div>
            {d.downloaded ? (
              <div className="font-mono text-[11px] text-text-secondary">
                {d.records?.toLocaleString("tr-TR")} kayıt · {size(d.bytes)}
                <br />
                {d.downloaded_at && new Date(d.downloaded_at).toLocaleString("tr-TR")}
                {d.stale && <span className="text-priority-medium-text"> · eskimiş</span>}
              </div>
            ) : (
              <div className="text-xs text-text-secondary">Henüz indirilmedi — ilgili modül ilk çalıştığında kendisi indirir.</div>
            )}
            {d.last_error && <div className="text-xs text-priority-critical-text">{d.last_error}</div>}
            <Button size="sm" variant="outline" className="mt-auto self-start" onClick={() => download(d.name)} disabled={d.downloading}>
              {d.downloading ? <Loader2 aria-hidden className="h-3.5 w-3.5 animate-spin" /> : <Download aria-hidden className="h-3.5 w-3.5" />}
              {d.downloading ? "İndiriliyor…" : d.downloaded ? "Yenile" : "İndir"}
            </Button>
          </li>
        ))}
      </ul>
    </section>
  );
}

function RecentRuns() {
  const { data, error, loading, reload } = useApi(() => api.enrichment.recent(60), []);
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-sm font-medium uppercase tracking-wide text-text-tertiary">Son koşular</h2>
      {loading && <SkeletonRows count={4} />}
      {error && <ErrorState error={error} onRetry={reload} />}
      {data && data.length === 0 && (
        <EmptyState title="Henüz koşu yok" description="Bir seçicinin sayfasındaki Zenginleştirme sekmesinden bir modül çalıştır." />
      )}
      {data && data.length > 0 && (
        <ul className="flex flex-col divide-y divide-border rounded-xl border border-border">
          {data.map((r) => (
            <li key={r.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2 text-sm">
              {r.status === "DONE" ? (
                <ShieldCheck aria-label="başarılı" className="h-4 w-4 text-confidence-supported-text" />
              ) : r.status === "FAILED" ? (
                <ShieldX aria-label="başarısız" className="h-4 w-4 text-priority-critical-text" />
              ) : (
                <Loader2 aria-label="çalışıyor" className="h-4 w-4 animate-spin text-text-tertiary" />
              )}
              <span className="text-foreground">{r.module_label}</span>
              <OpsecBadge opsec={r.opsec} />
              {r.target_type === "selector" ? (
                <Link href={selectorHref(r.target_id)} className="min-w-0 truncate font-mono text-xs text-text-secondary hover:text-foreground">
                  {r.target_id}
                </Link>
              ) : r.target_type === "claim" ? (
                <Link href={`/claims/view?id=${r.target_id.slice(6)}`} className="text-xs text-text-secondary hover:text-foreground">
                  claim
                </Link>
              ) : (
                <Link href={`/entities/${r.target_id.slice(7)}`} className="text-xs text-text-secondary hover:text-foreground">
                  entity
                </Link>
              )}
              <span className="ml-auto font-mono text-[11px] text-text-tertiary">{new Date(r.started_at).toLocaleString("tr-TR")}</span>
              {r.error && <span className="w-full text-xs text-priority-critical-text">{r.error}</span>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
