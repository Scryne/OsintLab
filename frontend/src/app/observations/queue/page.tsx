"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import {
  Archive,
  ArrowUpRight,
  Clock,
  FileText,
  Filter,
  ScanEye,
  Sparkles,
  Undo2,
} from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import type { ObservationQueue, QueueItem, SignalReason } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { ErrorState, EmptyState } from "@/components/ui/state";
import { SkeletonRows } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { InjectionWarning } from "@/components/provenance/injection-warning";
import { useToast } from "@/components/ui/toast";
import { QuickPromoteDialog } from "./quick-promote";
import { BulkPromoteDialog } from "./bulk-promote";

type Band = "all" | "high" | "noise";

/** Backend'in `HIGH_SIGNAL_THRESHOLD`'u. İlk istekte henüz yanıt elimizde olmadığı için
 * bilinen değerle başlıyoruz; yanıt gelince `high_signal_threshold` esas alınıyor, böylece
 * eşik iki yerde iki ayrı sayıya ayrışmıyor. Bantlar tam burada bölünüyor: `min_score`
 * kapsayıcı, `max_score` dışlayıcı. */
const DEFAULT_HIGH_BAND = 0.4;

/** Faz 16 — Promote Kuyruğu.
 *
 * Ölçüm (2026-09-05): 224 gözlemin 223'ü promote edilmemişti. Sebep "insan karar veriyor"
 * değil, kararın PAHALI olması: Faz 10'un promote diyaloğu tek gözlem üzerinden tam form
 * doldurtuyor, çünkü o zaman gözlemler elle ve teker teker giriliyordu. Faz 12 toplamayı
 * otomatikleştirince o yol fiilen kapandı.
 *
 * Bu sayfa kararı insandan almıyor; kararı ucuzlatıyor — sinyale göre sıralanmış tek ekran,
 * toplu eleme, ve önerilerle doldurulmuş kısa yol. */
export default function QueuePage() {
  const toast = useToast();
  const [band, setBand] = useState<Band>("all");
  const [host, setHost] = useState<string>("all");
  const [query, setQuery] = useState("");
  const [rawSelected, setRawSelected] = useState<string[]>([]);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  // Son elemenin geri alınabilmesi için. Toplu bir işlemin geri dönüşü yoksa kullanıcı onu
  // kullanmaz — kuyruğu eritmenin önündeki asıl engel "yanlış seçersem ne olur" tereddüdü.
  const [lastDismissed, setLastDismissed] = useState<string[]>([]);

  const { data, error, loading, reload } = useApi<ObservationQueue>(
    () =>
      api.observations.queue({
        limit: 1000,
        host: host === "all" ? undefined : host,
        minScore: band === "high" ? DEFAULT_HIGH_BAND : undefined,
        maxScore: band === "noise" ? DEFAULT_HIGH_BAND : undefined,
      }),
    [band, host]
  );

  const threshold = data?.high_signal_threshold ?? DEFAULT_HIGH_BAND;

  const items = useMemo(() => {
    if (!data) return [];
    const q = query.trim().toLowerCase();
    if (!q) return data.items;
    return data.items.filter(
      (i) => i.raw_content.toLowerCase().includes(q) || (i.source_url ?? "").toLowerCase().includes(q)
    );
  }, [data, query]);

  // Görünürlükten çıkan bir satır seçili SAYILMAZ: kullanıcı filtreyi değiştirdikten sonra
  // "Ele" dediğinde ekranda görmediği kayıtların elenmesi, geri alınabilir olsa bile bir
  // sürpriz olurdu. Seçim bir effect'le budanmıyor, TÜREVİ alınıyor — effect olsaydı bir
  // render boyunca "seçili ama görünmeyen" bir ara durum oluşurdu.
  const visibleIds = useMemo(() => new Set(items.map((i) => i.id)), [items]);
  const selected = useMemo(() => rawSelected.filter((id) => visibleIds.has(id)), [rawSelected, visibleIds]);

  // Toplu promote satırların KENDİSİNE ihtiyaç duyuyor (öneriler ve eşleşen entity'ler
  // orada), sadece id'lere değil.
  const selectedItems = useMemo(() => items.filter((i) => selected.includes(i.id)), [items, selected]);
  const allVisibleSelected = items.length > 0 && items.every((i) => selected.includes(i.id));
  const someSelected = selected.length > 0;

  function toggle(id: string, on: boolean) {
    setRawSelected((prev) => (on ? [...new Set([...prev, id])] : prev.filter((v) => v !== id)));
  }

  async function dismissSelected() {
    if (!selected.length) return;
    setBusy(true);
    try {
      const res = await api.observations.dismiss(selected, reason.trim() || null);
      setLastDismissed(selected);
      setRawSelected([]);
      toast(
        res.skipped.length
          ? `${res.dismissed} gözlem elendi · ${res.skipped.length} atlandı (zaten claim üretmiş)`
          : `${res.dismissed} gözlem elendi — silinmedi, "değerlendirildi" olarak işaretlendi`,
        "success"
      );
      reload();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Eleme başarısız", "error");
    } finally {
      setBusy(false);
    }
  }

  async function undoDismiss() {
    if (!lastDismissed.length) return;
    setBusy(true);
    try {
      const res = await api.observations.undismiss(lastDismissed);
      toast(`${res.dismissed} gözlem kuyruğa geri alındı`, "success");
      setLastDismissed([]);
      reload();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Geri alma başarısız", "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-[2rem] font-semibold tracking-tight text-foreground">
            Promote Kuyruğu
          </h1>
          <p className="max-w-2xl text-sm text-text-secondary">
            Otomatik tarama gözlem biriktiriyor; bilgiye dönüşmesi hâlâ senin kararın. Bu ekran
            kararı senden almıyor — sinyale göre sıralayıp ucuzlatıyor.
          </p>
        </div>
        <Link
          href="/observations"
          className="inline-flex items-center gap-1 text-xs text-text-secondary underline decoration-white/20 underline-offset-2 hover:text-foreground hover:decoration-white/50"
        >
          Tüm gözlemler
          <ArrowUpRight aria-hidden className="h-3 w-3" />
        </Link>
      </header>

      {data && <QueueHealth queue={data} />}

      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <Tabs value={band} onValueChange={(v) => v && setBand(v as Band)}>
            <TabsList>
              <TabsTrigger value="all">Tümü</TabsTrigger>
              <TabsTrigger value="high">Yüksek sinyal</TabsTrigger>
              <TabsTrigger value="noise">Gürültü adayı</TabsTrigger>
            </TabsList>
          </Tabs>

          <Select value={host} onValueChange={(v) => v && setHost(v)}>
            <SelectTrigger className="w-[15rem]" aria-label="Kaynak adresine göre filtrele">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tüm adresler</SelectItem>
              {(data?.stats.hosts ?? []).map((h) => (
                <SelectItem key={h.host} value={h.host}>
                  {h.host} · {h.count}
                  {h.high_signal > 0 ? ` (${h.high_signal} sinyalli)` : ""}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Metinde ara…"
            aria-label="Kuyrukta ara"
            className="max-w-[16rem]"
          />
        </div>

        {/* Toplu aksiyon şeridi — seçim varken yapışkan, çünkü 200 satırlık bir listede
            seçimi yaptığın yerle butonun olduğu yer aynı ekranda olmuyor. */}
        <div
          className={
            someSelected
              ? "glass-panel sticky top-3 z-20 flex flex-wrap items-center gap-3 rounded-xl px-4 py-3"
              : "flex flex-wrap items-center gap-3 rounded-xl border border-border bg-surface px-4 py-3"
          }
        >
          <Checkbox
            checked={allVisibleSelected}
            indeterminate={someSelected && !allVisibleSelected}
            onCheckedChange={(on) => setRawSelected(on ? items.map((i) => i.id) : [])}
            aria-label={allVisibleSelected ? "Görünen tüm gözlemlerin seçimini kaldır" : "Görünen tüm gözlemleri seç"}
          />
          <span className="text-sm text-text-secondary">
            {someSelected ? (
              <>
                <strong className="tabular-nums text-foreground">{selected.length}</strong> seçili
                {items.length !== selected.length && ` · ${items.length} görünen`}
              </>
            ) : (
              <>
                <span className="tabular-nums text-foreground">{items.length}</span> gözlem görünüyor
              </>
            )}
          </span>

          <div className="ml-auto flex flex-wrap items-center gap-2">
            {someSelected && (
              <Input
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Eleme gerekçesi (opsiyonel)"
                aria-label="Eleme gerekçesi"
                className="w-[16rem]"
              />
            )}
            <Button size="sm" variant="outline" onClick={dismissSelected} disabled={!someSelected || busy}>
              <Archive aria-hidden className="h-4 w-4" />
              Ele
            </Button>
            {/* Toplu promote, toplu elemenin yanında duruyor — ikisi de aynı kararın iki
                yönü ("bu bilgiye dönüşsün" / "dönüşmesin") ve ayrı yerlerde olsalardı
                kullanıcı biri için seçtiği kümeyi diğeri için yeniden seçerdi. */}
            <BulkPromoteDialog items={selectedItems} onDone={reload} />
            {lastDismissed.length > 0 && (
              <Button size="sm" variant="ghost" onClick={undoDismiss} disabled={busy}>
                <Undo2 aria-hidden className="h-4 w-4" />
                Son elemeyi geri al ({lastDismissed.length})
              </Button>
            )}
          </div>
        </div>

        {/* Eleme yıkıcı değil: kayıt silinmiyor, "değerlendirildi" işaretini alıyor. Bunu
            söylemek şart — yoksa kullanıcı 180 kaydı seçmeye cesaret edemez. */}
        <p className="flex items-start gap-1.5 text-xs leading-relaxed text-text-tertiary">
          <Filter aria-hidden className="mt-0.5 h-3 w-3 shrink-0" />
          Elenen gözlem <span className="font-medium text-text-secondary">silinmez</span> —
          &quot;değerlendirildi, bilgiye dönüştürülmedi&quot; olarak işaretlenir ve Gözlemler
          sayfasının &quot;Elendi&quot; sekmesinde durmaya devam eder.
        </p>
      </div>

      {loading && <SkeletonRows />}
      {error && <ErrorState message={error.message} onRetry={reload} />}
      {!loading && !error && data && items.length === 0 && (
        <EmptyState
          title={data.stats.pending === 0 ? "Kuyruk boş" : "Bu filtrede gözlem yok"}
          description={
            data.stats.pending === 0
              ? "Bekleyen gözlem kalmadı — biriken her kayıt ya bilgiye dönüştü ya değerlendirilip elendi."
              : "Filtreyi genişlet."
          }
        />
      )}

      {!loading && items.length > 0 && (
        <ol className="flex flex-col gap-2">
          {items.map((item) => (
            <li key={item.id}>
              <QueueRow
                item={item}
                threshold={threshold}
                selected={selected.includes(item.id)}
                onToggle={(on) => toggle(item.id, on)}
                onPromoted={reload}
              />
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

/** Kuyruk sağlığı. Roadmap'in Faz 16 maddesindeki eksik: "221 rakamı ancak API'ye elle
 * sorulunca çıktı" — bekleyen sayısını görmenin hiçbir yolu yoktu. */
function QueueHealth({ queue }: { queue: ObservationQueue }) {
  const { stats } = queue;
  return (
    <div className="glass-panel grid grid-cols-2 gap-px overflow-hidden rounded-xl sm:grid-cols-4">
      <Stat label="Bekleyen" value={stats.pending} tone="foreground" />
      <Stat label="Yüksek sinyal" value={stats.high_signal} tone="accent" />
      <Stat label="Gürültü adayı" value={stats.noise} tone="muted" />
      <Stat
        label="En eski bekleyen"
        value={stats.oldest_pending_age_days === null ? "—" : `${stats.oldest_pending_age_days} gün`}
        tone={(stats.oldest_pending_age_days ?? 0) >= 7 ? "warn" : "muted"}
        icon={Clock}
      />
      <div className="col-span-2 flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-2.5 text-xs text-text-tertiary sm:col-span-4">
        <span>
          Değerlendirilmiş: <span className="tabular-nums text-text-secondary">{stats.evaluated}</span>
        </span>
        <span>
          Elenmiş: <span className="tabular-nums text-text-secondary">{stats.dismissed}</span>
        </span>
        <span>
          Toplam gözlem: <span className="tabular-nums text-text-secondary">{stats.total}</span>
        </span>
        {stats.total > 0 && (
          <span className="ml-auto">
            Kuyruk eritildi:{" "}
            <span className="tabular-nums text-text-secondary">
              {Math.round(((stats.total - stats.pending) / stats.total) * 100)}%
            </span>
          </span>
        )}
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  tone,
  icon: Icon,
}: {
  label: string;
  value: number | string;
  tone: "foreground" | "accent" | "muted" | "warn";
  icon?: React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>;
}) {
  const toneClass =
    tone === "accent"
      ? "text-[var(--brand-accent)]"
      : tone === "warn"
        ? "text-priority-medium"
        : tone === "muted"
          ? "text-text-secondary"
          : "text-foreground";
  return (
    <div className="flex flex-col gap-0.5 bg-surface px-4 py-3">
      <span className="flex items-center gap-1.5 text-[11px] uppercase tracking-wide text-text-tertiary">
        {Icon && <Icon aria-hidden className="h-3 w-3" />}
        {label}
      </span>
      <span className={`font-display text-2xl font-semibold tabular-nums ${toneClass}`}>{value}</span>
    </div>
  );
}

const HEADLINE_LIMIT = 160;

function headline(text: string): string {
  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (trimmed) return trimmed.length > HEADLINE_LIMIT ? `${trimmed.slice(0, HEADLINE_LIMIT)}…` : trimmed;
  }
  return "(boş gözlem)";
}

function QueueRow({
  item,
  threshold,
  selected,
  onToggle,
  onPromoted,
}: {
  item: QueueItem;
  threshold: number;
  selected: boolean;
  onToggle: (on: boolean) => void;
  onPromoted: () => void;
}) {
  const [open, setOpen] = useState(false);
  const high = item.signal_score >= threshold;

  return (
    <div
      className={`flex gap-3 rounded-lg border bg-surface p-3 transition-colors ${
        selected ? "border-[var(--brand-accent)]/50 bg-white/[0.07]" : "border-border hover:bg-surface-raised"
      }`}
    >
      <div className="pt-0.5">
        <Checkbox checked={selected} onCheckedChange={onToggle} aria-label={`Seç: ${headline(item.raw_content)}`} />
      </div>

      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <div className="flex items-start justify-between gap-3">
          <p className="min-w-0 text-sm text-foreground">{headline(item.raw_content)}</p>
          <SignalChip score={item.signal_score} high={high} />
        </div>

        <InjectionWarning hits={item.injection_hits} />

        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[11px] text-text-tertiary">
          <span>{new Date(item.created_at).toLocaleString("tr-TR")}</span>
          {item.age_days > 0 && <span>{item.age_days} gündür bekliyor</span>}
          {item.host && <span>{item.host}</span>}
          {item.from_evidence && (
            <span className="inline-flex items-center gap-1">
              <FileText aria-hidden className="h-3 w-3" />
              {item.from_evidence.file_name ?? "belge"} · s{item.from_evidence.page_from}
            </span>
          )}
          {item.text_source === "ocr" && (
            <span className="inline-flex items-center gap-1 text-priority-medium">
              <ScanEye aria-hidden className="h-3 w-3" />
              OCR
            </span>
          )}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2">
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            className="text-xs text-text-tertiary underline decoration-white/20 underline-offset-2 hover:text-foreground"
          >
            {open ? "Gerekçeleri gizle" : `Neden bu sırada? (${item.signal_reasons.length})`}
          </button>
          <QuickPromoteDialog item={item} onPromoted={onPromoted} />
        </div>

        {open && (
          <div className="flex flex-col gap-2 rounded-lg border border-border bg-black/20 p-3">
            <ul className="flex flex-col gap-1.5">
              {item.signal_reasons.length === 0 && (
                <li className="text-xs text-text-tertiary">
                  Hiçbir sinyal yok — bildiğimiz bir entity&apos;ye değmiyor, tanınan bir kaynaktan
                  gelmiyor, elle girilmemiş.
                </li>
              )}
              {item.signal_reasons.map((reason) => (
                <ReasonLine key={reason.code} reason={reason} />
              ))}
            </ul>
            {/* Gözlem metni burada tam olarak açılıyor: promote kararı bu satırda veriliyor
                ve başlık tek başına yetmeyebilir. */}
            <details className="text-xs">
              <summary className="cursor-pointer text-text-tertiary hover:text-foreground">
                Ham metnin tamamı ({item.raw_content.length.toLocaleString("tr-TR")} karakter)
              </summary>
              {/* Q22: toplanan içerik talimat değildir — sınır içinde, ham veri olarak. */}
              <p className="mt-2 max-h-64 overflow-y-auto whitespace-pre-wrap border-l-2 border-white/10 pl-3 text-text-secondary">
                {item.raw_content}
              </p>
              {item.source_url && (
                <p className="mt-2 break-all font-mono text-[11px] text-text-tertiary">{item.source_url}</p>
              )}
            </details>
          </div>
        )}
      </div>
    </div>
  );
}

function ReasonLine({ reason }: { reason: SignalReason }) {
  const informational = reason.weight === 0;
  return (
    <li className="flex items-start gap-2 text-xs leading-relaxed">
      <span
        className={`mt-px shrink-0 rounded px-1.5 py-0.5 font-mono text-[10px] tabular-nums ${
          informational ? "bg-priority-medium/15 text-priority-medium" : "bg-white/10 text-text-secondary"
        }`}
      >
        {informational ? "uyarı" : `+${reason.weight.toFixed(2)}`}
      </span>
      <span className="text-text-secondary">{reason.text}</span>
    </li>
  );
}

function SignalChip({ score, high }: { score: number; high: boolean }) {
  return (
    <Badge variant={high ? "secondary" : "outline"} className="shrink-0 gap-1 tabular-nums">
      {high && <Sparkles aria-hidden className="h-3 w-3 text-[var(--brand-accent)]" />}
      {score.toFixed(2)}
    </Badge>
  );
}
