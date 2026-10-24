"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, Eye, FileJson, Loader2, Play, RotateCw, ShieldCheck, ShieldX, Zap } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import type { EnrichmentModule, EnrichmentRun } from "@/lib/types-pivot";
import { Button } from "@/components/ui/button";
import { ConfirmButton } from "@/components/ui/confirm-button";
import { EmptyState, ErrorState } from "@/components/ui/state";
import { SkeletonRows } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { OpsecBadge } from "@/components/pivot/opsec-badge";
import { RunSummary } from "@/components/pivot/run-summary";
import { SelectorChip } from "@/components/pivot/selector-chip";
import { cn } from "@/lib/utils";

function ago(iso: string | null | undefined): string {
  if (!iso) return "";
  const ms = Date.now() - new Date(iso).getTime();
  const m = Math.round(ms / 60000);
  if (m < 1) return "az önce";
  if (m < 60) return `${m} dk önce`;
  const h = Math.round(m / 60);
  if (h < 48) return `${h} sa önce`;
  return `${Math.round(h / 24)} gün önce`;
}

/** Faz 30 — bir hedefin (seçici ya da `entity:<id>`) zenginleştirme paneli.
 *
 * Koşu arka planda başlatılır ve RUNNING bir koşu varken panel 2 sn'de bir yoklar: Wayback ve
 * crt.sh gibi kaynaklar ölçümde dakikaları buldu, arayüz bunu donarak beklememeli.
 *
 * OPSEC görünür: her modülün pasif/aktif/yerel sınıfı rozette, aktif modül iki adımlı onay ister,
 * "hepsini çalıştır" yalnızca pasif ve yerel modülleri kapsar. Önbellekteki bir sonuç tekrar
 * sorulmaz — "Yeniden sor" açık bir karar. */
export function EnrichmentPanel({
  targetId,
  onPivotsChanged,
  onSuggest,
}: {
  targetId: string;
  onPivotsChanged?: () => void;
  onSuggest?: (kind: string, value: string) => void;
}) {
  const toast = useToast();
  const [polling, setPolling] = useState(false);
  const { data, error, loading, reload } = useApi(
    async () => {
      const mods = await api.enrichment.forTarget(targetId);
      const running = mods.some((m) => m.last_run?.status === "RUNNING");
      setPolling((was) => {
        // Bir koşu bittiğinde pivotlar değişmiş olabilir — üst sayfa tazelensin.
        if (was && !running) onPivotsChanged?.();
        return running;
      });
      return mods;
    },
    [targetId],
    { pollMs: polling ? 2000 : undefined }
  );

  async function start(mod: EnrichmentModule, opts?: { force?: boolean; confirm_active?: boolean }) {
    try {
      const run = await api.enrichment.run(mod.name, targetId, opts);
      if (run.cached) toast(`${mod.label}: önbellekteki sonuç gösteriliyor (${ago(run.finished_at)})`, "default");
      setPolling(true);
      reload();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Başlatılamadı", "error");
    }
  }

  async function runAllPassive() {
    const mods = (data ?? []).filter((m) => m.enabled && m.opsec !== "ACTIVE" && m.last_run?.status !== "RUNNING");
    for (const m of mods) {
      try {
        await api.enrichment.run(m.name, targetId);
      } catch {
        // Tek tek hata gösterilmez; her modülün kartı kendi sonucunu söyler.
      }
    }
    toast(`${mods.length} pasif/yerel modül başlatıldı`, "default");
    setPolling(true);
    reload();
  }

  if (loading) return <SkeletonRows count={4} />;
  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (!data?.length) return <EmptyState title="Bu tür için modül yok" description="Bu seçici türünü zenginleştiren bir kaynak henüz eklenmedi; dış araç bağlantılarını kullan." />;

  const done = data.filter((m) => m.last_run?.status === "DONE").length;
  const passiveCount = data.filter((m) => m.enabled && m.opsec !== "ACTIVE").length;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-text-secondary" aria-live="polite">
          <span className="tabular-nums text-foreground">{done}</span>/{data.length} modül sonuç verdi.
          {polling && (
            <span className="ml-2 inline-flex items-center gap-1 text-text-tertiary">
              <Loader2 aria-hidden className="h-3 w-3 animate-spin" /> çalışıyor
            </span>
          )}
        </p>
        <Button size="sm" variant="secondary" onClick={runAllPassive} disabled={passiveCount === 0}>
          <Zap aria-hidden className="h-3.5 w-3.5" />
          Pasif modüllerin hepsini çalıştır
        </Button>
      </div>
      <ul className="flex flex-col gap-2">
        {data.map((mod) => (
          <ModuleCard key={mod.name} mod={mod} onStart={start} onPivotsChanged={onPivotsChanged} onSuggest={onSuggest} />
        ))}
      </ul>
    </div>
  );
}

function ModuleCard({
  mod,
  onStart,
  onPivotsChanged,
  onSuggest,
}: {
  mod: EnrichmentModule;
  onStart: (m: EnrichmentModule, opts?: { force?: boolean; confirm_active?: boolean }) => void;
  onPivotsChanged?: () => void;
  onSuggest?: (kind: string, value: string) => void;
}) {
  const run = mod.last_run ?? null;
  const [open, setOpen] = useState(run?.status === "DONE");
  const running = run?.status === "RUNNING";
  const active = mod.opsec === "ACTIVE";

  return (
    <li className={cn("rounded-lg border border-border bg-surface", !mod.enabled && "opacity-60")}>
      <div className="flex flex-wrap items-start gap-3 p-3">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          disabled={!run}
          aria-expanded={open}
          className="flex min-w-0 flex-1 items-start gap-2 text-left disabled:cursor-default"
        >
          {run ? (
            open ? <ChevronDown aria-hidden className="mt-0.5 h-4 w-4 shrink-0 text-text-tertiary" /> : <ChevronRight aria-hidden className="mt-0.5 h-4 w-4 shrink-0 text-text-tertiary" />
          ) : (
            <span className="w-4 shrink-0" />
          )}
          <span className="min-w-0">
            <span className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium text-foreground">{mod.label}</span>
              <OpsecBadge opsec={mod.opsec} title={mod.opsec_note} />
              <span className="text-xs text-text-tertiary">{mod.provider}</span>
            </span>
            <span className="mt-0.5 block text-xs text-pretty text-text-secondary">{mod.description}</span>
            {run && (
              <span className="mt-1 flex items-center gap-1.5 text-[11px] text-text-tertiary">
                {run.status === "DONE" && <ShieldCheck aria-hidden className="h-3 w-3 text-confidence-supported-text" />}
                {run.status === "FAILED" && <ShieldX aria-hidden className="h-3 w-3 text-priority-critical-text" />}
                {running ? "çalışıyor…" : run.status === "FAILED" ? `başarısız · ${ago(run.finished_at)}` : `${ago(run.finished_at)}`}
                {run.pivots && run.pivots.length > 0 && ` · ${run.pivots.length} pivot`}
              </span>
            )}
          </span>
        </button>
        <div className="flex shrink-0 items-center gap-1.5">
          {!mod.enabled ? (
            <span className="text-xs text-text-tertiary">Kapalı — Zenginleştirme ayarları</span>
          ) : running ? (
            <Button size="sm" variant="outline" disabled>
              <Loader2 aria-hidden className="h-3.5 w-3.5 animate-spin" />
              Çalışıyor
            </Button>
          ) : active ? (
            <ConfirmButton
              onConfirm={() => onStart(mod, { confirm_active: true, force: !!run })}
              confirmLabel="Hedefin sunucusuna istek atılacak."
              confirmAction="İsteği gönder"
            >
              <Play aria-hidden className="h-3.5 w-3.5" />
              {run ? "Yeniden" : "Çalıştır"}
            </ConfirmButton>
          ) : run ? (
            <Button size="sm" variant="ghost" onClick={() => onStart(mod, { force: true })} title="Önbelleği yok sayıp kaynağa yeniden sor">
              <RotateCw aria-hidden className="h-3.5 w-3.5" />
              Yeniden sor
            </Button>
          ) : (
            <Button size="sm" variant="outline" onClick={() => onStart(mod)}>
              <Play aria-hidden className="h-3.5 w-3.5" />
              Çalıştır
            </Button>
          )}
        </div>
      </div>
      {open && run && run.status !== "RUNNING" && (
        <div className="flex flex-col gap-3 border-t border-border p-3">
          <RunSummary run={run} onSuggest={onSuggest} />
          {run.pivots && run.pivots.length > 0 && (
            <div className="flex flex-col gap-1.5">
              <h4 className="text-[11px] font-medium uppercase tracking-wide text-text-tertiary">Bu koşunun açtığı pivotlar</h4>
              <div className="flex flex-wrap gap-1.5">
                {run.pivots.slice(0, 40).map((p) => {
                  const otherId = p.to_id === run.target_id ? p.from_id : p.to_id;
                  const otherValue = p.to_id === run.target_id ? p.from_value : p.to_value;
                  const otherKind = otherId.split(":")[0] as typeof p.to_kind;
                  return (
                    <span key={`${p.from_id}-${p.to_id}-${p.relation}`} className="inline-flex items-center gap-1">
                      <span className="text-[10px] text-text-tertiary">{p.relation}</span>
                      <SelectorChip id={otherId} kind={otherKind} value={otherValue} />
                    </span>
                  );
                })}
              </div>
            </div>
          )}
          <RunFooter run={run} onConverted={onPivotsChanged} />
        </div>
      )}
    </li>
  );
}

function RunFooter({ run, onConverted }: { run: EnrichmentRun; onConverted?: () => void }) {
  const toast = useToast();
  const [raw, setRaw] = useState<{ integrity_ok: boolean; record: Record<string, unknown> } | null>(null);
  const [busy, setBusy] = useState(false);

  async function showRaw() {
    if (raw) return setRaw(null);
    try {
      setRaw(await api.enrichment.raw(run.id));
    } catch (err) {
      toast(err instanceof Error ? err.message : "Ham kayıt okunamadı", "error");
    }
  }

  async function toObservation() {
    setBusy(true);
    try {
      await api.enrichment.toObservation(run.id);
      toast("Gözlem oluşturuldu — Promote Kuyruğu'nda değerlendirilebilir", "success");
      onConverted?.();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Gözleme çevrilemedi", "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-text-tertiary">
        <span>{new Date(run.finished_at ?? run.started_at).toLocaleString("tr-TR")}</span>
        {run.raw_sha256 && (
          <span className="font-mono" title="Ham yanıt dosyasının SHA-256'sı">
            sha256 {run.raw_sha256.slice(0, 16)}…
          </span>
        )}
        <button type="button" onClick={showRaw} className="inline-flex items-center gap-1 hover:text-foreground">
          <FileJson aria-hidden className="h-3 w-3" />
          {raw ? "Ham kaydı gizle" : "Ham kayıt"}
        </button>
        {run.status === "DONE" && (
          <button type="button" onClick={toObservation} disabled={busy} className="inline-flex items-center gap-1 hover:text-foreground disabled:opacity-50">
            <Eye aria-hidden className="h-3 w-3" />
            Gözleme çevir
          </button>
        )}
      </div>
      {raw && (
        <div className="flex flex-col gap-1">
          <p className={cn("text-xs", raw.integrity_ok ? "text-confidence-supported-text" : "text-priority-critical-text")}>
            {raw.integrity_ok ? "Bütünlük doğrulandı: dosya koşudan beri değişmemiş." : "Bütünlük BOZUK: dosya koşudan sonra değişmiş."}
          </p>
          <pre className="max-h-80 overflow-auto rounded-md border border-border bg-black/40 p-2 font-mono text-[11px] leading-relaxed text-text-secondary">
            {JSON.stringify(raw.record, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
