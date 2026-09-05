"use client";

import { useMemo, useState } from "react";
import { AlertTriangle, ArrowUp, Check, SkipForward, Zap } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import type { ObservationPromoteBatchResult, QueueItem } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { SearchablePicker } from "@/components/forms/searchable-picker";
import { useToast } from "@/components/ui/toast";
import { SingleSourceNote } from "@/components/provenance/single-source-note";

type Mode = "suggested" | "uniform";

/** Faz 16 (ikinci tur) — toplu promote.
 *
 * İlk tur kuyruğu kurdu ve toplu ELEMEYİ ucuzlattı; ilk gerçek kullanımda çıkan şikâyet
 * promote tarafıydı: 21 kayıt aynı kaynağa (`openai.com` resmi duyuruları) ve aynı entity'ye
 * bağlanacaktı, yani aynı iki alan 21 kez onaylanacaktı — kapatılmaya çalışılan darboğazın
 * küçültülmüş hali.
 *
 * Design Principle #7 ile çelişmiyor: bu otomatik bir kural değil. Kümeyi kullanıcı seçiyor,
 * ne olacağını önceden görüyor (aşağıdaki gruplama), ve kararı bir kez veriyor. */
export function BulkPromoteDialog({
  items,
  onDone,
}: {
  items: QueueItem[];
  onDone: () => void;
}) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<Mode>("suggested");
  const [sourceId, setSourceId] = useState<string | null>(null);
  const [entityId, setEntityId] = useState<string | null>(null);
  const [requireEntity, setRequireEntity] = useState(true);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ObservationPromoteBatchResult | null>(null);

  const { data: sources } = useApi(() => (open ? api.sources.list() : Promise.resolve([])), [open]);
  const { data: entities } = useApi(() => (open ? api.entities.list() : Promise.resolve([])), [open]);

  /** Kümenin önizlemesi: hangi kayıt hangi kaynak+entity ile gidecek, hangileri atlanacak.
   * Backend'in kararını burada tekrar etmiyoruz — aynı önerileri kuyruk yanıtı zaten
   * taşıyor; bu yalnızca onların gruplanmış hali. */
  const preview = useMemo(() => {
    const groups = new Map<string, { source: string; entity: string; count: number }>();
    const blocked: { headline: string; reason: string }[] = [];
    // Tek kaynak modunda henüz kaynak seçilmediyse önizleme yapılmıyor: her kaydı "kaynak
    // yok" diye listelemek, kullanıcının kendi seçmediği bir alanı veri hatası gibi
    // gösterirdi.
    if (mode === "uniform" && !sourceId) return { groups: [], blocked: [] };
    for (const item of items) {
      const source = mode === "uniform" ? sourceLabel(sources, sourceId) : item.suggested_source_name;
      // Öneri modunda entity adı kuyruk yanıtından geliyor (`matched_entities`), ayrıca
      // entity listesinin yüklenmesini beklemiyor — beklenseydi diyalog ilk açıldığında her
      // kayıt bir an "entity bağı yok" görünürdü.
      const entity =
        mode === "uniform"
          ? entityLabel(entities, entityId)
          : item.matched_entities[0]?.name ?? null;
      const head = firstLine(item.raw_content);
      if (!source) {
        blocked.push({ headline: head, reason: `${item.host ?? "adressiz"} için kayıtlı kaynak yok` });
        continue;
      }
      if (requireEntity && !entity) {
        blocked.push({ headline: head, reason: "entity bağı çözülemedi" });
        continue;
      }
      // Ayrac NUL: veride gecemeyecegi icin cakismasiz bir birlestirme anahtari verir.
      // Kacis dizisiyle yaziliyor — kaynaga HAM byte olarak konursa git ve ripgrep
      // dosyayi ikili sayiyor ve her metin taramasindan sessizce dusuyor (bu dosya
      // tam da bu yuzden 2026-09-06 denetiminde iki kez atlandi). Davranis ayni.
      const key = `${source}\u0000${entity ?? "—"}`;
      const group = groups.get(key) ?? { source, entity: entity ?? "—", count: 0 };
      group.count += 1;
      groups.set(key, group);
    }
    return { groups: [...groups.values()].sort((a, b) => b.count - a.count), blocked };
  }, [items, mode, sourceId, entityId, requireEntity, sources, entities]);

  const willPromote = preview.groups.reduce((n, g) => n + g.count, 0);
  const canRun = willPromote > 0 && (mode === "suggested" || !!sourceId);

  async function run() {
    setBusy(true);
    try {
      const res = await api.observations.promoteBatch({
        observationIds: items.map((i) => i.id),
        sourceId: mode === "uniform" ? sourceId : null,
        entityId: mode === "uniform" ? entityId : null,
        requireEntity,
      });
      setResult(res);
      toast(
        `${res.promoted + res.below_threshold} claim üretildi` +
          (res.skipped ? ` · ${res.skipped} atlandı` : ""),
        res.promoted + res.below_threshold > 0 ? "success" : "default"
      );
      onDone();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Toplu promote başarısız", "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) {
          setResult(null);
          setMode("suggested");
          setSourceId(null);
          setEntityId(null);
        }
      }}
    >
      <DialogTrigger
        render={
          <Button size="sm" disabled={items.length === 0}>
            <Zap aria-hidden className="h-4 w-4" />
            Promote et
          </Button>
        }
      />
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {result ? "Toplu promote sonucu" : `${items.length} gözlemi promote et`}
          </DialogTitle>
          <DialogDescription>Seçili gözlemleri tek seferde claim&apos;e yükseltir. Kaynak ve entity tüm kümeye birlikte uygulanır.</DialogDescription>
        </DialogHeader>

        {result ? (
          <BatchResult result={result} />
        ) : (
          <div className="flex max-h-[60vh] flex-col gap-4 overflow-y-auto pr-1">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="bulk-mode">Kaynak ve entity</Label>
              <Select value={mode} onValueChange={(v) => v && setMode(v as Mode)}>
                <SelectTrigger id="bulk-mode">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="suggested">Her kayıt kendi önerisini kullansın</SelectItem>
                  <SelectItem value="uniform">Hepsine aynısını uygula</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {mode === "uniform" && (
              <>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="bulk-promote-kaynak-tu-m-ku-me-1">Kaynak (tüm küme)</Label>
                  <SearchablePicker
                    id="bulk-promote-kaynak-tu-m-ku-me-1"
                    items={(sources ?? []).map((s) => ({ id: s.id, label: s.name, sublabel: s.source_type }))}
                    value={sourceId}
                    onChange={setSourceId}
                    placeholder="Kaynak ara…"
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="bulk-promote-entity-tu-m-ku-me-2">Entity (tüm küme)</Label>
                  <SearchablePicker
                    id="bulk-promote-entity-tu-m-ku-me-2"
                    items={(entities ?? []).map((e) => ({ id: e.id, label: e.name, sublabel: e.entity_type }))}
                    value={entityId}
                    onChange={setEntityId}
                    placeholder="Entity ara…"
                  />
                </div>
              </>
            )}

            {/* Önizleme, "ne olacağını görmeden onayla" durumunu ortadan kaldırıyor: toplu bir
                işlemde asıl risk yanlış kararı vermek değil, verdiğin kararın kaç kaydı ve
                hangi bağla etkilediğini bilmemek. */}
            <div className="flex flex-col gap-2 rounded-lg border border-border bg-surface p-3">
              <p className="text-[11px] uppercase tracking-wide text-text-tertiary">Ne olacak</p>
              {preview.groups.length === 0 && (
                <p className="text-sm text-text-secondary">
                  Bu ayarlarla promote edilecek kayıt yok.
                </p>
              )}
              <ul className="flex flex-col gap-1">
                {preview.groups.map((g) => (
                  <li key={`${g.source}-${g.entity}`} className="flex items-start gap-2 text-sm">
                    <span className="mt-px shrink-0 rounded bg-white/10 px-1.5 py-0.5 font-mono text-[10px] tabular-nums text-text-secondary">
                      {g.count}
                    </span>
                    <span className="text-text-secondary">
                      <span className="text-foreground">{g.source}</span> → {g.entity}
                    </span>
                  </li>
                ))}
              </ul>
            </div>

            <label className="flex cursor-pointer items-start gap-2.5 text-xs leading-relaxed text-text-secondary">
              <span className="mt-0.5">
                <Checkbox
                  checked={requireEntity}
                  onCheckedChange={setRequireEntity}
                  aria-label="Entity bağı olmayan kayıtları atla"
                />
              </span>
              <span>
                <span className="font-medium text-foreground">Entity bağı olmayan kaydı atla.</span>{" "}
                Bağsız claim yalıtık kalır — Memory Recall onu bulamaz, entity sayfasında ve
                Obsidian notunda görünmez. Toplu bir işlemde bu, onlarca kayda birden ve sessizce
                olur; o yüzden varsayılan açık.
              </span>
            </label>

            {preview.blocked.length > 0 && (
              <div className="flex flex-col gap-1.5 rounded-lg border border-priority-medium/30 bg-priority-medium/5 p-3">
                <p className="flex items-center gap-1.5 text-xs font-medium text-priority-medium-text">
                  <AlertTriangle aria-hidden className="h-3.5 w-3.5" />
                  {preview.blocked.length} kayıt atlanacak
                </p>
                <ul className="flex flex-col gap-0.5">
                  {preview.blocked.slice(0, 6).map((b) => (
                    <li key={b.headline} className="text-xs text-text-tertiary">
                      {b.headline.slice(0, 55)} — {b.reason}
                    </li>
                  ))}
                  {preview.blocked.length > 6 && (
                    <li className="text-xs text-text-tertiary">…ve {preview.blocked.length - 6} tane daha</li>
                  )}
                </ul>
                <p className="text-xs leading-relaxed text-text-tertiary">
                  Atlanan kayıt kuyrukta kalır; tek tek &quot;Hızlı promote&quot; ile eksik bağı
                  orada kurabilirsin.
                </p>
              </div>
            )}
          </div>
        )}

        <DialogFooter>
          {result ? (
            <Button onClick={() => setOpen(false)}>Kapat</Button>
          ) : (
            <Button onClick={run} disabled={busy || !canRun}>
              {busy ? "Yükseltiliyor…" : `${willPromote} kaydı promote et`}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function BatchResult({ result }: { result: ObservationPromoteBatchResult }) {
  const skipped = result.items.filter((i) => i.status === "SKIPPED");
  const below = result.items.filter((i) => i.status === "BELOW_THRESHOLD");
  return (
    <div className="flex max-h-[60vh] flex-col gap-4 overflow-y-auto pr-1">
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        <ResultStat icon={Check} label="SUPPORTED" value={result.promoted} tone="ok" />
        <ResultStat icon={ArrowUp} label="REPORTED" value={result.below_threshold} tone="muted" />
        <ResultStat icon={SkipForward} label="Atlandı" value={result.skipped} tone="warn" />
      </div>

      {below.length > 0 && <SingleSourceNote />}

      {skipped.length > 0 && (
        <div className="flex flex-col gap-1.5">
          <p className="text-[11px] uppercase tracking-wide text-text-tertiary">
            Atlananlar — kuyrukta kaldılar
          </p>
          <ul className="flex flex-col gap-1.5">
            {skipped.map((i) => (
              <li key={i.observation_id} className="text-xs leading-relaxed">
                <span className="text-foreground">{i.headline.slice(0, 60)}</span>
                <br />
                <span className="text-text-tertiary">{i.message}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function ResultStat({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>;
  label: string;
  value: number;
  tone: "ok" | "muted" | "warn";
}) {
  const toneClass =
    tone === "ok" ? "text-confidence-supported-text" : tone === "warn" ? "text-priority-medium-text" : "text-text-secondary";
  return (
    <div className="flex flex-col gap-0.5 rounded-lg border border-border bg-surface px-3 py-2">
      <span className="flex items-center gap-1 text-[10px] uppercase tracking-wide text-text-tertiary">
        <Icon aria-hidden className="h-3 w-3" />
        {label}
      </span>
      <span className={`font-display text-xl font-semibold tabular-nums ${toneClass}`}>{value}</span>
    </div>
  );
}

function firstLine(text: string): string {
  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (trimmed) return trimmed;
  }
  return "(boş gözlem)";
}

function sourceLabel(sources: { id: string; name: string }[] | null, id: string | null): string | null {
  if (!id) return null;
  return sources?.find((s) => s.id === id)?.name ?? null;
}

function entityLabel(entities: { id: string; name: string }[] | null, id: string | null): string | null {
  if (!id) return null;
  return entities?.find((e) => e.id === id)?.name ?? null;
}
