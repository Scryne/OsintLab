"use client";

import { useState } from "react";
import Link from "next/link";
import { Plus, Rss, X } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import type { CollectorFetchResult } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ErrorState, EmptyState } from "@/components/ui/state";
import { Skeleton } from "@/components/ui/skeleton";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { WireframeGlobe } from "@/components/ui/wireframe-globe";
import { ScanSchedules } from "@/components/forms/scan-schedules";

export default function CollectorsPage() {
  const toast = useToast();
  const { data: allowlist, error, loading, reload } = useApi(() => api.collectors.allowlist(), []);
  const [hostname, setHostname] = useState("");
  const [adding, setAdding] = useState(false);

  async function addHostname() {
    if (!hostname.trim()) return;
    setAdding(true);
    try {
      await api.collectors.addAllowlist(hostname.trim());
      toast(`${hostname.trim()} allowlist'e eklendi`, "success");
      setHostname("");
      reload();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Eklenemedi", "error");
    } finally {
      setAdding(false);
    }
  }

  async function removeHostname(host: string) {
    try {
      await api.collectors.removeAllowlist(host);
      toast(`${host} kaldırıldı`, "default");
      reload();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Kaldırılamadı", "error");
    }
  }

  return (
    <div className="relative isolate mx-auto flex max-w-2xl flex-col gap-8 overflow-hidden">
      <WireframeGlobe spin className="pointer-events-none absolute -right-16 -top-16 -z-10 h-56 w-56 text-white/5" />
      <div>
        <h1 className="font-display text-[2rem] font-semibold tracking-tight text-foreground">Toplayıcılar</h1>
        <p className="text-sm text-text-secondary">
          Allowlist&apos;teki hostname&apos;lerden RSS/web sayfası tara — sonuçlar Gözlem olarak sisteme düşer.
          Bir kaynağı zamanlanmış taramaya alırsan bunu senin yerine arka plan yapar.
        </p>
      </div>

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-medium uppercase tracking-wide text-text-tertiary">Allowlist</h2>
        <div className="flex gap-2">
          <Input
            value={hostname}
            onChange={(e) => setHostname(e.target.value)}
            placeholder="ör. feeds.bbci.co.uk"
            onKeyDown={(e) => e.key === "Enter" && addHostname()}
          />
          <Button onClick={addHostname} disabled={adding || !hostname.trim()}>
            <Plus aria-hidden className="h-4 w-4" />
            Ekle
          </Button>
        </div>
        {loading && (
          <div className="flex flex-wrap gap-1.5">
            <Skeleton className="h-7 w-28 rounded-full" />
            <Skeleton className="h-7 w-24 rounded-full" />
            <Skeleton className="h-7 w-32 rounded-full" />
          </div>
        )}
        {error && <ErrorState message={error.message} onRetry={reload} />}
        {!loading && !error && (!allowlist || allowlist.hostnames.length === 0) && (
          <EmptyState title="Allowlist boş" description="Taramak istediğin bir hostname ekle." />
        )}
        <div className="flex flex-wrap gap-1.5">
          {allowlist?.hostnames.map((host) => (
            <span
              key={host}
              className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface px-2.5 py-1 font-mono text-xs text-foreground"
            >
              {host}
              <button type="button" onClick={() => removeHostname(host)} aria-label={`${host} kaldır`} className="text-text-tertiary hover:text-priority-critical">
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-medium uppercase tracking-wide text-text-tertiary">Tek Seferlik Tarama</h2>
        <FetchForm hostnames={allowlist?.hostnames ?? []} />
      </section>

      <ScanSchedules />
    </div>
  );
}

function FetchForm({ hostnames }: { hostnames: string[] }) {
  const [url, setUrl] = useState("");
  const [mode, setMode] = useState<"rss" | "web">("rss");
  const [limit, setLimit] = useState("50");
  const [sinceDays, setSinceDays] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CollectorFetchResult | null>(null);

  async function submit() {
    if (!url.trim()) return;
    setSubmitting(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.collectors.fetch(url.trim(), mode, {
        limit: Number(limit) || 50,
        since_days: sinceDays.trim() ? Number(sinceDays) : null,
      });
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bilinmeyen hata");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4">
      {hostnames.length === 0 && (
        <p className="text-xs text-text-tertiary">Önce yukarıdan bir hostname allowlist&apos;e ekle.</p>
      )}
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="collector-url">URL</Label>
        <Input id="collector-url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://…" />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label>Mod</Label>
        <Select value={mode} onValueChange={(v) => v && setMode(v as "rss" | "web")}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="rss">RSS feed</SelectItem>
            <SelectItem value="web">Tek web sayfası</SelectItem>
          </SelectContent>
        </Select>
      </div>
      {mode === "rss" && (
        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="collector-limit">En fazla kaç öğe</Label>
            <Input
              id="collector-limit"
              type="number"
              min={1}
              max={500}
              value={limit}
              onChange={(e) => setLimit(e.target.value)}
            />
            <p className="text-xs text-text-tertiary">En yeniden başlayarak. Bazı feed&apos;ler tüm arşivi yayınlar.</p>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="collector-since">Son kaç gün</Label>
            <Input
              id="collector-since"
              type="number"
              min={1}
              value={sinceDays}
              onChange={(e) => setSinceDays(e.target.value)}
              placeholder="hepsi"
            />
            <p className="text-xs text-text-tertiary">Boş bırakılırsa tarih filtresi uygulanmaz.</p>
          </div>
        </div>
      )}
      <Button onClick={submit} disabled={submitting || !url.trim()} className="self-start">
        <Rss aria-hidden className="h-4 w-4" />
        {submitting ? "Taranıyor…" : "Tara"}
      </Button>
      {error && <p className="text-sm text-priority-critical">{error}</p>}
      {result && (
        <div className="rounded-lg border border-border bg-surface-raised p-3 text-sm">
          <p className="text-foreground">
            {result.observations_created} gözlem oluşturuldu
          </p>
          <p className="mt-1 text-xs text-text-secondary">
            Kaynakta {result.items_available} öğe · {result.items_considered} tanesi değerlendirildi
            {result.duplicates_skipped > 0 && ` · ${result.duplicates_skipped} kopya atlandı`}
          </p>
          <p className="mt-1 break-all font-mono text-xs text-text-tertiary">{result.final_url}</p>
          <Link href="/observations" className="mt-1 inline-block text-xs text-text-secondary underline decoration-white/20 underline-offset-2 hover:text-foreground hover:decoration-white/50">
            Gözlemlere git →
          </Link>
        </div>
      )}
    </div>
  );
}
