"use client";

import { Suspense, useState, useMemo } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Inbox as InboxIcon, Plus, X } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import type { Observation, ObservationPromoteResult } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { ErrorState, EmptyState } from "@/components/ui/state";
import { SkeletonRows } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { SearchablePicker } from "@/components/forms/searchable-picker";
import { ConfidenceBadge } from "@/components/provenance/confidence";
import { ProvenanceBlock } from "@/components/provenance/provenance-label";
import { useToast } from "@/components/ui/toast";

type Filter = "all" | "promoted" | "pending";

/** `useSearchParams` (F58'in ids filtresi) statik ön-render'ı bozuyor; Next.js bunun bir
 * Suspense sınırı içinde olmasını istiyor. Sayfa kabuğu dışarıda, arama parametresini okuyan
 * gövde içeride. */
export default function ObservationsPage() {
  return (
    <Suspense fallback={<div className="mx-auto max-w-3xl"><SkeletonRows /></div>}>
      <ObservationsView />
    </Suspense>
  );
}

function ObservationsView() {
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const promoted = filter === "all" ? undefined : filter === "promoted";
  // F58: Inbox'taki bir tarama bildiriminden "bu 17 gözlemi göster" diye gelinebiliyor.
  // Bildirim hangi gözlemlerden bahsettiğini zaten biliyordu; eksik olan aradaki bağdı.
  const searchParams = useSearchParams();
  const idsParam = searchParams.get("ids");
  const ids = useMemo(() => (idsParam ? idsParam.split(",").filter(Boolean) : []), [idsParam]);
  const { data: observations, error, loading, reload } = useApi(
    () => api.observations.list({ promoted, ids: ids.length ? ids : undefined }),
    [promoted, idsParam]
  );

  // Faz 11 (dogfooding F10): tek bir collector taraması bile onlarca gözlem üretiyor
  // (gerçek bir feed'de yüzlerce). Metin araması olmadan belirli bir gözlemi bulmak
  // elle kaydırmaya kalıyordu.
  const filtered = useMemo(() => {
    if (!observations) return [];
    const q = query.trim().toLowerCase();
    if (!q) return observations;
    return observations.filter(
      (o) =>
        o.raw_content.toLowerCase().includes(q) ||
        (o.source_url ?? "").toLowerCase().includes(q)
    );
  }, [observations, query]);

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="font-display text-[2rem] font-semibold tracking-tight text-foreground">Gözlemler</h1>
          <p className="text-sm text-text-secondary">
            Ham metin/haber yapıştır, sisteme sok — eşiği geçerse Knowledge Graph&apos;a Claim olarak yükselir.
          </p>
        </div>
        <NewObservationDialog onCreated={reload} />
      </div>

      {ids.length > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-surface px-4 py-3">
          <p className="flex items-center gap-2 text-sm text-text-secondary">
            <InboxIcon aria-hidden className="h-4 w-4 shrink-0 text-text-tertiary" />
            Bir Inbox bildiriminden gelen <strong className="text-foreground">{ids.length}</strong> gözlem
            gösteriliyor.
          </p>
          <Link
            href="/observations"
            className="inline-flex items-center gap-1 text-xs text-text-secondary underline decoration-white/20 underline-offset-2 hover:text-foreground hover:decoration-white/50"
          >
            <X aria-hidden className="h-3 w-3" />
            Filtreyi kaldır
          </Link>
        </div>
      )}

      <Tabs value={filter} onValueChange={(v) => v && setFilter(v as Filter)}>
        <TabsList>
          <TabsTrigger value="all">Tümü</TabsTrigger>
          <TabsTrigger value="pending">Bekliyor</TabsTrigger>
          <TabsTrigger value="promoted">Promote edildi</TabsTrigger>
        </TabsList>
        <TabsContent value={filter} className="mt-4 flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Gözlem metninde veya kaynak adresinde ara…"
              aria-label="Gözlemlerde ara"
            />
            {observations && observations.length > 0 && (
              <span className="shrink-0 text-xs tabular-nums text-text-tertiary">
                {query.trim() ? `${filtered.length} / ${observations.length}` : `${observations.length} kayıt`}
              </span>
            )}
          </div>
          {loading && <SkeletonRows />}
          {error && <ErrorState message={error.message} onRetry={reload} />}
          {!loading && !error && (!observations || observations.length === 0) && (
            <EmptyState title="Bu filtrede gözlem yok" />
          )}
          {!loading && !error && observations && observations.length > 0 && filtered.length === 0 && (
            <EmptyState title="Eşleşen gözlem yok" description="Arama terimini değiştir." />
          )}
          {!loading && (
            <div className="flex flex-col gap-2">
              {filtered.map((o) => (
                <ObservationRow key={o.id} observation={o} onPromoted={reload} />
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function ObservationRow({ observation, onPromoted }: { observation: Observation; onPromoted: () => void }) {
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border bg-surface p-3">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm text-foreground">{observation.raw_content}</p>
        {/* F32: üç durum var, iki rozet yetmiyordu — "işlendi ama eşiği geçmedi" hâli
            "hiç işlenmemiş" gibi görünüyordu. */}
        <Badge
          variant={observation.promoted ? "secondary" : observation.produced_claim_id ? "secondary" : "outline"}
          className="shrink-0"
        >
          {observation.promoted
            ? "promoted"
            : observation.produced_claim_id
              ? "claim üretildi · eşik altı"
              : "bekliyor"}
        </Badge>
      </div>
      <div className="flex items-center justify-between gap-3">
        <p className="font-mono text-[11px] text-text-tertiary">
          {new Date(observation.created_at).toLocaleString("tr-TR")}
          {observation.source_url && <> · {observation.source_url}</>}
        </p>
        <PromoteDialog observation={observation} onPromoted={onPromoted} />
      </div>
    </div>
  );
}

function NewObservationDialog({ onCreated }: { onCreated: () => void }) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [rawContent, setRawContent] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (!rawContent.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.observations.create({ raw_content: rawContent.trim(), source_url: sourceUrl.trim() || null });
      toast("Gözlem eklendi", "success");
      setRawContent("");
      setSourceUrl("");
      setOpen(false);
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bilinmeyen hata");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button size="sm">
            <Plus aria-hidden className="h-4 w-4" />
            Yeni Gözlem
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Yeni gözlem ekle</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="observation-content">Ham metin</Label>
            <Textarea
              id="observation-content"
              value={rawContent}
              onChange={(e) => setRawContent(e.target.value)}
              placeholder="Haber metni, sosyal medya paylaşımı vb…"
              rows={5}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="observation-source-url">Kaynak URL (opsiyonel)</Label>
            <Input
              id="observation-source-url"
              value={sourceUrl}
              onChange={(e) => setSourceUrl(e.target.value)}
              placeholder="https://…"
            />
          </div>
          {error && <p className="text-sm text-priority-critical">{error}</p>}
        </div>
        <DialogFooter>
          <Button onClick={submit} disabled={submitting || !rawContent.trim()}>
            {submitting ? "Ekleniyor…" : "Ekle"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function PromoteDialog({ observation, onPromoted }: { observation: Observation; onPromoted: () => void }) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const { data: sources } = useApi(() => api.sources.list(), [open]);
  const { data: entities } = useApi(() => api.entities.list(), [open]);
  const { data: events } = useApi(() => api.events.list(), [open]);
  const { data: evidenceList } = useApi(() => api.evidence.list(), [open]);
  const { data: claims } = useApi(() => api.claims.list(), [open]);

  const [sourceId, setSourceId] = useState<string | null>(null);
  // Faz 11 (dogfooding F15): varsayılan "none"du ve alan sessizce atlanabiliyordu. Atlanınca
  // claim graf'ta yalıtık kalıyor — Memory Recall (Faz 4) onu bulamıyor, entity sayfasında ve
  // vault notunda görünmüyor; üstelik hiçbir uyarı yok. En yaygın durum entity bağlamak.
  const [aboutType, setAboutType] = useState<"none" | "entity" | "event">("entity");
  const [aboutId, setAboutId] = useState<string | null>(null);
  const [evidenceIds, setEvidenceIds] = useState<string[]>([]);
  const [contradictingIds, setContradictingIds] = useState<string[]>([]);
  const [corroborates, setCorroborates] = useState<string[]>([]);
  // Faz 11 (dogfooding F26): bu iki alan promote diyaloğunda yoktu — sadece "Yeni Claim"
  // formunda vardı. Ama toplanan veriden Claim'e giden TEK yol promote; yani collector'dan
  // gelen bir claim ne çelişkili işaretlenebiliyor ne de eski bir claim'i supersede
  // edebiliyordu. Faz 2'nin çelişki/temporal motoru bu boru hattında hiç çalışmamıştı.
  const [contradicts, setContradicts] = useState<string[]>([]);
  const [supersedes, setSupersedes] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ObservationPromoteResult | null>(null);

  const sourceItems = (sources ?? []).map((s) => ({ id: s.id, label: s.name, sublabel: s.source_type }));
  const aboutItems =
    aboutType === "entity"
      ? (entities ?? []).map((e) => ({ id: e.id, label: e.name, sublabel: e.entity_type }))
      : (events ?? []).map((e) => ({ id: e.id, label: e.title, sublabel: e.event_type }));
  const evidenceItems = (evidenceList ?? []).map((e) => ({ id: e.id, label: e.evidence_type, sublabel: e.file_path ?? undefined }));
  const claimItems = (claims ?? []).map((c) => ({ id: c.id, label: c.text.slice(0, 60) }));

  async function submit() {
    if (!sourceId) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.observations.promote(observation.id, {
        source_id: sourceId,
        about_entity_id: aboutType === "entity" ? aboutId : null,
        about_event_id: aboutType === "event" ? aboutId : null,
        evidence_ids: evidenceIds,
        contradicting_evidence_ids: contradictingIds,
        corroborates,
        contradicts,
        supersedes,
      });
      setResult(res);
      toast(
        res.claim.confidence >= 0.45
          ? "Claim'e yükseltildi"
          : "Claim oluşturuldu (eşik altı) — gözlem ham haliyle de duruyor",
        res.claim.confidence >= 0.45 ? "success" : "default"
      );
      onPromoted();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bilinmeyen hata");
    } finally {
      setSubmitting(false);
    }
  }

  function reset() {
    setSourceId(null);
    setAboutType("entity");
    setAboutId(null);
    setEvidenceIds([]);
    setContradictingIds([]);
    setCorroborates([]);
    setError(null);
    setResult(null);
  }

  // F32: eşiği geçmeyen bir promote de claim üretir ve ikinci promote 409 döner. Buton
  // durmaya devam edince tekrar denemek doğal oluyordu — artık claim üretilmiş her gözlemde
  // gizleniyor, sadece `promoted` olanlarda değil.
  if (observation.promoted || observation.produced_claim_id) return null;

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) reset();
      }}
    >
      <DialogTrigger render={<Button size="sm">Promote</Button>} />
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Observation&apos;ı Claim&apos;e yükselt</DialogTitle>
        </DialogHeader>

        {result ? (
          <div className="flex max-h-[60vh] flex-col gap-4 overflow-y-auto pr-1">
            <div className="rounded-lg border border-border bg-surface p-3">
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm text-foreground">{result.claim.text}</p>
                <ConfidenceBadge state={result.claim.knowledge_state} confidence={result.claim.confidence} className="shrink-0" />
              </div>
            </div>
            {result.claim.confidence < 0.45 && (
              <p className="text-xs text-text-tertiary">
                Eşik (%45) geçilmedi — claim oluşturuldu ama gözlem &quot;promoted&quot; işaretlenmedi, ham haliyle erişilebilir kalıyor.
              </p>
            )}
            {result.why_matters.length > 0 && (
              <div className="flex flex-col gap-1.5">
                {result.why_matters.map((reason, i) => (
                  <ProvenanceBlock key={i} type="SYSTEM_INFERENCE">
                    {reason.text}
                  </ProvenanceBlock>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="flex max-h-[60vh] flex-col gap-4 overflow-y-auto pr-1">
            <div className="flex flex-col gap-1.5">
              <Label>Kaynak</Label>
              <SearchablePicker items={sourceItems} value={sourceId} onChange={setSourceId} placeholder="Kaynak ara…" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>İlgili entity/event</Label>
              <Select
                value={aboutType}
                onValueChange={(v) => {
                  if (!v) return;
                  setAboutType(v as "none" | "entity" | "event");
                  setAboutId(null);
                }}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">Yok</SelectItem>
                  <SelectItem value="entity">Entity</SelectItem>
                  <SelectItem value="event">Event</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {aboutType !== "none" && (
              <SearchablePicker items={aboutItems} value={aboutId} onChange={setAboutId} placeholder="Ara…" />
            )}
            {(aboutType === "none" || !aboutId) && (
              <p className="rounded-lg border border-priority-high/30 bg-priority-high/5 px-3 py-2 text-xs leading-relaxed text-text-secondary">
                <span className="font-medium text-foreground">Bağlanmazsa bu claim yalıtık kalır.</span>{" "}
                Memory Recall onu bulamaz, entity sayfasında ve Obsidian vault notunda görünmez.
                Claim oluşturulduktan sonra bu bağ <span className="font-medium">şu an</span> değiştirilemiyor.
              </p>
            )}
            <div className="flex flex-col gap-1.5">
              <Label>Destekleyici kanıt (opsiyonel)</Label>
              <SearchablePicker items={evidenceItems} value={evidenceIds} onChange={setEvidenceIds} multiple placeholder="Kanıt ara…" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Çelişen kanıt (opsiyonel)</Label>
              <SearchablePicker
                items={evidenceItems}
                value={contradictingIds}
                onChange={setContradictingIds}
                multiple
                placeholder="Kanıt ara…"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Doğruladığı claim&apos;ler (opsiyonel)</Label>
              <SearchablePicker items={claimItems} value={corroborates} onChange={setCorroborates} multiple placeholder="Claim ara…" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Çeliştiği claim&apos;ler (opsiyonel)</Label>
              <SearchablePicker items={claimItems} value={contradicts} onChange={setContradicts} multiple placeholder="Claim ara…" />
              {contradicts.length > 0 && (
                <p className="text-xs leading-relaxed text-text-tertiary">
                  Her iki claim de <span className="font-medium text-foreground">CONTRADICTED</span> durumuna geçer
                  ve çelişki <span className="font-medium text-foreground">UNRESOLVED</span> olarak kaydedilir —
                  eski bilgi silinmez.
                </p>
              )}
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Yerini aldığı claim (opsiyonel)</Label>
              <SearchablePicker items={claimItems} value={supersedes} onChange={setSupersedes} placeholder="Claim ara…" />
              {supersedes && (
                <p className="text-xs leading-relaxed text-text-tertiary">
                  Eski claim silinmez; <span className="font-medium text-foreground">valid_to</span> alanı kapatılır.
                </p>
              )}
            </div>
            {error && <p className="text-sm text-priority-critical">{error}</p>}
          </div>
        )}

        <DialogFooter>
          {result ? (
            <Button onClick={() => setOpen(false)}>Kapat</Button>
          ) : (
            <Button onClick={submit} disabled={submitting || !sourceId}>
              {submitting ? "Yükseltiliyor…" : "Promote et"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
