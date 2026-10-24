"use client";

import { useState } from "react";
import Link from "next/link";
import { AlertTriangle, BellOff, Clock, Pause, Play, Plus, Trash2, Zap } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import type { ScanSchedule } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ConfirmButton } from "@/components/ui/confirm-button";
import { ErrorState, EmptyState } from "@/components/ui/state";
import { SkeletonRows } from "@/components/ui/skeleton";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { SearchablePicker } from "@/components/forms/searchable-picker";
import { useToast } from "@/components/ui/toast";

/** Faz 11'de öğrenilen kullanım desenine göre seçilmiş aralıklar: bir OSINT feed'i saatlik
 * kontrol edilecek bir borsa ekranı değil. Varsayılan 3 saat — "birkaç saat içinde haberim
 * olsun" ihtiyacını karşılayan, yayıncıya karşı da kaba olmayan aralık (bkz. backend
 * `DEFAULT_SCAN_INTERVAL_MINUTES`). */
const INTERVALS = [
  { value: "30", label: "30 dakikada bir" },
  { value: "60", label: "Saatte bir" },
  { value: "180", label: "3 saatte bir" },
  { value: "360", label: "6 saatte bir" },
  { value: "720", label: "12 saatte bir" },
  { value: "1440", label: "Günde bir" },
] as const;

function formatInterval(minutes: number): string {
  if (minutes < 60) return `${minutes} dk`;
  const hours = minutes / 60;
  if (hours < 24) return `${Number(hours.toFixed(1))} sa`;
  return `${Number((hours / 24).toFixed(1))} gün`;
}

/** Mutlak zaman damgası yerine "2 sa önce / ~40 dk sonra": bir zamanlayıcıda önemli olan
 * an değil, aradaki mesafe. Tam damga `title` olarak duruyor. */
function relativeTime(iso: string): string {
  const diffMs = new Date(iso).getTime() - Date.now();
  const past = diffMs < 0;
  const mins = Math.round(Math.abs(diffMs) / 60000);
  const text = mins < 1 ? "az önce" : mins < 60 ? `${mins} dk` : mins < 1440 ? `${Math.round(mins / 60)} sa` : `${Math.round(mins / 1440)} gün`;
  if (mins < 1) return text;
  return past ? `${text} önce` : `${text} sonra`;
}

/** Faz 13: liste formdan ayrıldı — kaynak detay sayfası da aynı satırları (durum, hata,
 * "şimdi tara", duraklat) göstermek zorunda. Aynı bilgiyi iki ayrı yerde ayrı ayrı render
 * etmek, Faz 11'in F19/F43/F46 kalıbıyla aynı tuzak olurdu: unutulan her yer bozuk çıktı. */
export function ScanScheduleList({ sourceId, emptyText }: { sourceId?: string; emptyText?: string }) {
  const toast = useToast();
  const { data: all, error, loading, reload } = useApi(() => api.collectors.schedules(), []);
  const schedules = sourceId ? all?.filter((s) => s.source_id === sourceId) : all;

  return (
    <div className="flex flex-col gap-2">
      {loading && <SkeletonRows count={2} />}
      {error && <ErrorState error={error} onRetry={reload} />}
      {!loading && !error && schedules?.length === 0 && (
        <EmptyState
          title="Zamanlanmış tarama yok"
          description={
            emptyText ??
            "Bir kaynağı periyodik taramaya alırsan, yeni içerik için elle tarama yapmana gerek kalmaz."
          }
        />
      )}
      {schedules?.map((s) => (
        <ScheduleRow key={s.id} schedule={s} onChanged={reload} toast={toast} />
      ))}
    </div>
  );
}

export function ScanSchedules() {
  const [showForm, setShowForm] = useState(false);
  // Liste kendi verisini çekiyor; form bir tarama kurunca `key` değiştirilerek yeniden
  // monte ediliyor (bu kadarı için ayrı bir state paylaşımı kurmaya değmez).
  const [listKey, setListKey] = useState(0);

  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-medium uppercase tracking-wide text-text-tertiary">
            Zamanlanmış Taramalar
          </h2>
          <p className="mt-0.5 text-xs text-text-tertiary">
            Kurulan tarama arka planda kendi çalışır — yeni içerik Gözlem&apos;e, izlenen kaynaklarda
            Inbox&apos;a düşer.
          </p>
        </div>
        <Button size="sm" variant={showForm ? "ghost" : "outline"} onClick={() => setShowForm((s) => !s)}>
          <Plus aria-hidden className="h-4 w-4" />
          {showForm ? "Vazgeç" : "Yeni"}
        </Button>
      </div>

      {showForm && (
        <ScheduleForm
          onCreated={() => {
            setShowForm(false);
            setListKey((k) => k + 1);
          }}
        />
      )}

      <ScanScheduleList key={listKey} />
    </section>
  );
}

function ScheduleRow({
  schedule,
  onChanged,
  toast,
}: {
  schedule: ScanSchedule;
  onChanged: () => void;
  toast: (message: string, variant?: "default" | "success" | "error") => void;
}) {
  const [busy, setBusy] = useState(false);
  const failing = schedule.last_status === "ERROR";

  async function act(fn: () => Promise<unknown>, ok: string) {
    setBusy(true);
    try {
      await fn();
      toast(ok, "success");
      onChanged();
    } catch (err) {
      toast(err instanceof Error ? err.message : "İşlem başarısız", "error");
    } finally {
      setBusy(false);
    }
  }

  async function runNow() {
    setBusy(true);
    try {
      const res = await api.collectors.runSchedule(schedule.id);
      // Tarama hatası HTTP hatası değil (koşu kaydedildi) — kullanıcıya yine de hata olarak
      // gösteriliyor, yoksa "çalıştı" sanır.
      if (res.status === "ERROR") toast(res.error ?? "Tarama başarısız", "error");
      else if (res.observations_created === 0) toast("Tarandı — yeni içerik yok", "default");
      else toast(`${res.observations_created} yeni gözlem`, "success");
      onChanged();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Tarama başarısız", "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-sm font-medium text-foreground">
              {schedule.label || schedule.source_name || "Adsız tarama"}
            </span>
            <Badge variant="outline" className="uppercase">{schedule.mode}</Badge>
            <Badge variant="outline">
              <Clock aria-hidden className="h-3 w-3" />
              {formatInterval(schedule.interval_minutes)}
            </Badge>
            {!schedule.active && <Badge variant="secondary">Duraklatıldı</Badge>}
            {/* Çalışan ama hiçbir şey söylemeyen bir tarama sessiz bir tuzak — Monitor
                kapalıysa bunu listede açıkça yazıyoruz. */}
            {schedule.active && !schedule.monitored && (
              <Badge variant="secondary" className="text-priority-medium-text">
                <BellOff aria-hidden className="h-3 w-3" />
                Inbox&apos;a düşmez
              </Badge>
            )}
          </div>
          <p className="mt-1 break-all font-mono text-xs text-text-tertiary">{schedule.url}</p>
          <StatusLine schedule={schedule} />
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          <Button size="sm" variant="outline" disabled={busy} onClick={runNow} className="h-7 px-2 text-xs">
            <Zap aria-hidden className="h-3.5 w-3.5" />
            Şimdi tara
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={busy}
            className="h-7 px-2 text-xs"
            onClick={() =>
              act(
                () => api.collectors.updateSchedule(schedule.id, { active: !schedule.active }),
                schedule.active ? "Duraklatıldı" : "Yeniden başlatıldı"
              )
            }
          >
            {schedule.active ? <Pause aria-hidden className="h-3.5 w-3.5" /> : <Play aria-hidden className="h-3.5 w-3.5" />}
            {schedule.active ? "Duraklat" : "Sürdür"}
          </Button>
          <ConfirmButton
            confirmLabel="Bu zamanlanmış tarama duracak"
            confirmAction="Taramayı kaldır"
            onConfirm={() => act(() => api.collectors.deleteSchedule(schedule.id), "Tarama kaldırıldı")}
            aria-label="Taramayı kaldır"
          >
            <Trash2 aria-hidden className="h-3.5 w-3.5" />
          </ConfirmButton>
        </div>
      </div>

      {failing && schedule.last_error && (
        <div className="mt-3 flex items-start gap-2 rounded-md border border-priority-critical/30 bg-priority-critical/5 p-2.5 text-xs">
          <AlertTriangle aria-hidden className="mt-0.5 h-3.5 w-3.5 shrink-0 text-priority-critical-text" />
          <div className="min-w-0">
            <p className="text-text-secondary">{schedule.last_error}</p>
            {schedule.consecutive_failures > 1 && (
              <p className="mt-1 text-text-tertiary">
                {schedule.consecutive_failures} kez üst üste — tekrar deneme aralığı otomatik uzatıldı.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function StatusLine({ schedule }: { schedule: ScanSchedule }) {
  return (
    <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-text-tertiary">
      {schedule.last_run_at ? (
        <span title={new Date(schedule.last_run_at).toLocaleString("tr-TR")}>
          Son koşu {relativeTime(schedule.last_run_at)}
          {schedule.last_status === "OK" &&
            ` · ${schedule.last_new_count ?? 0} yeni gözlem`}
        </span>
      ) : (
        <span>Henüz çalışmadı</span>
      )}
      {schedule.active && schedule.next_run_at && (
        <span title={new Date(schedule.next_run_at).toLocaleString("tr-TR")}>
          Sıradaki {relativeTime(schedule.next_run_at)}
        </span>
      )}
      <Link
        href="/observations"
        className="text-text-secondary underline decoration-white/20 underline-offset-2 hover:text-foreground hover:decoration-white/50"
      >
        gözlemler →
      </Link>
    </div>
  );
}

function ScheduleForm({ onCreated }: { onCreated: () => void }) {
  const toast = useToast();
  const { data: sources } = useApi(() => api.sources.list(), []);
  const [sourceId, setSourceId] = useState<string | null>(null);
  const [url, setUrl] = useState("");
  const [mode, setMode] = useState<"rss" | "web" | "telegram">("rss");
  const [interval, setInterval] = useState("180");
  const [itemLimit, setItemLimit] = useState("20");
  const [sinceDays, setSinceDays] = useState("7");
  const [watch, setWatch] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const selectedSource = sources?.find((s) => s.id === sourceId) ?? null;

  async function submit() {
    if (!sourceId) return;
    setSubmitting(true);
    try {
      await api.collectors.createSchedule({
        source_id: sourceId,
        url: url.trim() || null,
        mode,
        interval_minutes: Number(interval),
        item_limit: Number(itemLimit) || 20,
        since_days: sinceDays.trim() ? Number(sinceDays) : null,
        watch,
      });
      toast("Tarama kuruldu — ilk koşu birkaç dakika içinde", "success");
      onCreated();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Kurulamadı", "error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="scan-schedule-kaynak">Kaynak</Label>
        {/* Kaynak zorunlu: toplanan gözlemin provenance'ı ve Inbox bildiriminin izlenen
            hedefi bu. Kaynaksız bir tarama, sonradan promote edilemeyen içerik biriktirirdi. */}
        <SearchablePicker
          id="scan-schedule-kaynak"
          items={(sources ?? []).map((s) => ({ id: s.id, label: s.name, sublabel: s.url ?? undefined }))}
          value={sourceId}
          onChange={setSourceId}
          placeholder="Kaynak ara…"
          emptyText="Önce Kaynaklar sayfasından bir kaynak ekle"
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="schedule-url">Taranacak adres</Label>
        <Input
          id="schedule-url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder={selectedSource?.url ? `${selectedSource.url} (kaynağın adresi)` : "https://…/feed/"}
        />
        <p className="text-xs text-text-tertiary">
          Boş bırakılırsa kaynağın kendi adresi kullanılır. Feed adresi genelde farklıdır (ör.{" "}
          <span className="font-mono">/feed/</span>). Hostname allowlist&apos;te olmalı.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="scan-schedules-mod-1">Mod</Label>
          <Select value={mode} items={{ rss: "RSS feed", web: "Tek web sayfası", telegram: "Telegram kanalı (herkese açık)" }} onValueChange={(v) => v && setMode(v as "rss" | "web" | "telegram")}>
            <SelectTrigger id="scan-schedules-mod-1">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="rss">RSS feed</SelectItem>
              <SelectItem value="web">Tek web sayfası</SelectItem>
                <SelectItem value="telegram">Telegram kanalı (herkese açık)</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="scan-schedules-siklik-2">Sıklık</Label>
          <Select value={interval} items={INTERVALS} onValueChange={(v) => v && setInterval(v)}>
            <SelectTrigger id="scan-schedules-siklik-2">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {INTERVALS.map((i) => (
                <SelectItem key={i.value} value={i.value}>
                  {i.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {mode !== "web" && (
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="schedule-limit">Koşu başına en fazla öğe</Label>
            <Input
              id="schedule-limit"
              type="number"
              min={1}
              max={500}
              value={itemLimit}
              onChange={(e) => setItemLimit(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="schedule-since">Son kaç gün</Label>
            <Input
              id="schedule-since"
              type="number"
              min={1}
              value={sinceDays}
              onChange={(e) => setSinceDays(e.target.value)}
              placeholder="hepsi"
            />
          </div>
        </div>
      )}

      <label className="flex items-start gap-2 text-sm text-text-secondary">
        <input
          type="checkbox"
          checked={watch}
          onChange={(e) => setWatch(e.target.checked)}
          className="mt-0.5 h-4 w-4 rounded border-border bg-surface accent-white"
        />
        <span>
          Bu kaynağı izlemeye al
          <span className="block text-xs text-text-tertiary">
            Kapalıysa tarama yine çalışır ama Inbox&apos;a hiçbir şey düşmez — yeni içerikleri
            Gözlemler sayfasından elle kontrol etmen gerekir.
          </span>
        </span>
      </label>

      <Button onClick={submit} disabled={submitting || !sourceId} className="self-start">
        <Clock aria-hidden className="h-4 w-4" />
        {submitting ? "Kuruluyor…" : "Taramayı kur"}
      </Button>
    </div>
  );
}
