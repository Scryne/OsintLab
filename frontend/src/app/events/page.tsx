"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { CalendarClock, MapPin, Plus, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import type { EventCandidate, EventItem } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ErrorState, EmptyState } from "@/components/ui/state";
import { SkeletonList } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ConfidenceBadge } from "@/components/provenance/confidence";
import { TypeCombo } from "@/components/forms/type-combo";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast";
import { WireframeBurst } from "@/components/ui/wireframe-burst";

// Öneri listesi, kural değil — backend `event_type`'ı serbest bırakır (bkz. TypeCombo).
const EVENT_TYPE_SUGGESTIONS = [
  "lansman",
  "kesinti",
  "güvenlik olayı",
  "açıklama",
  "dava",
  "satın alma",
  "saldırı",
  "yaptırım",
];

type Tab = "events" | "candidates";

/** Claim metni promote akışından başlık + gövde olarak tek alanda geliyor; listede yalnızca
 *  ilk satır okunur bir özet verir. */
function excerpt(text: string): string {
  return text.split("\n")[0].trim();
}

/** Faz 18 — Event Katmanı.
 *
 * Ölçüm (2026-09-05): 43 canlı claim'in 43'ü entity'ye, 0'ı event'e bağlıydı ve grafta
 * sıfır event vardı. Sebep ilgisizlik değil erişilemezlikti — `/events` altında yalnızca
 * `[id]` sayfası vardı: liste yok, form yok, nav girişi yok. Promote formundaki "Event"
 * seçeneği görünüyor ama seçilecek hiçbir şey olmadığı için kullanılamıyordu.
 *
 * Sonuç: 43 claim'in 33'ü tek bir entity'ye (OpenAI) asılmıştı — lansman, kesinti, davalar,
 * rogue agent olayları hep aynı kovada. Doğal ayrıştırma ekseni tam olarak eksik olan şeydi.
 */
export default function EventsPage() {
  const [tab, setTab] = useState<Tab>("events");
  const { data: events, error, loading, reload } = useApi(() => api.events.list(), []);
  const {
    data: candidates,
    loading: candidatesLoading,
    reload: reloadCandidates,
  } = useApi(() => api.events.candidates(2), []);

  const candidateCount = candidates?.length ?? 0;

  const sorted = useMemo(() => {
    // Olaylar zaman çizgisidir: en yeni olan başta. `occurred_at` yoksa kayıt tarihine
    // düşülür — ikisini karıştırmamak için kartta hangisinin gösterildiği ayrıca yazılıyor.
    return [...(events ?? [])].sort(
      (a, b) =>
        new Date(b.occurred_at ?? b.created_at).getTime() - new Date(a.occurred_at ?? a.created_at).getTime()
    );
  }, [events]);

  function afterCreate() {
    reload();
    reloadCandidates();
  }

  return (
    <div className="relative isolate mx-auto flex max-w-4xl flex-col gap-6 overflow-hidden">
      <WireframeBurst spin className="pointer-events-none absolute -right-10 top-12 -z-10 h-48 w-48 text-white/5" />
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="font-display text-[2rem] font-semibold tracking-tight text-balance text-foreground">
            Olaylar
          </h1>
          <p className="max-w-2xl text-sm leading-relaxed text-text-secondary">
            Toplanan verinin çoğu bir olay hakkındadır: bir lansman, bir kesinti, bir dava.
            Claim&apos;i olaya bağlamak, tek bir entity&apos;de yığılan iddiaları okunur hale getirir —
            entity olaya <span className="text-foreground">karışan</span> taraf olarak bağlı kalır.
          </p>
        </div>
        <NewEventDialog onCreated={afterCreate} existingTypes={events?.map((e) => e.event_type) ?? []} />
      </header>

      <Tabs value={tab} onValueChange={(v) => v && setTab(v as Tab)}>
        <TabsList>
          <TabsTrigger value="events">Olaylar{sorted.length > 0 ? ` · ${sorted.length}` : ""}</TabsTrigger>
          <TabsTrigger value="candidates">
            Olay adayları{candidateCount > 0 ? ` · ${candidateCount}` : ""}
          </TabsTrigger>
        </TabsList>
      </Tabs>

      {tab === "events" && (
        <>
          {loading && <SkeletonList />}
          {error && <ErrorState message={error.message} onRetry={reload} />}
          {!loading && !error && sorted.length === 0 && (
            <EmptyState
              title="Henüz olay yok"
              description="Doğrulama kümelerinden hazır olay adaylarını gözden geçir, ya da sağ üstten elle bir olay kur."
              action={
                candidateCount > 0 ? (
                  <Button size="sm" variant="outline" onClick={() => setTab("candidates")}>
                    <Sparkles aria-hidden className="h-4 w-4" />
                    {candidateCount} adayı gör
                  </Button>
                ) : undefined
              }
            />
          )}
          {!loading && sorted.length > 0 && (
            <ol className="flex flex-col gap-2">
              {sorted.map((event) => (
                <li key={event.id}>
                  <EventCard event={event} />
                </li>
              ))}
            </ol>
          )}
        </>
      )}

      {tab === "candidates" && (
        <>
          <p className="text-sm leading-relaxed text-text-secondary">
            Bu adaylar yeni bir sinyalden değil, senin kurduğun doğrulama bağlarından geliyor:
            birbirini doğrulayan claim&apos;lerin oluşturduğu her küme bir olay adayı. Küme bir
            <span className="text-foreground"> öneri</span>dir — başlığı sen verirsin, kümeye ait
            olmayan claim&apos;i çıkarabilirsin.
          </p>
          {candidatesLoading && <SkeletonList />}
          {!candidatesLoading && candidateCount === 0 && (
            <EmptyState
              title="Olay adayı yok"
              description="Aday üretmek için önce Doğrulama ekranında birbirini doğrulayan claim'leri bağla; bağlı her küme burada olay adayı olur."
              action={
                <Link
                  href="/corroboration"
                  className="text-sm text-text-secondary underline decoration-white/20 underline-offset-2 hover:text-foreground hover:decoration-white/50"
                >
                  Doğrulama ekranına git →
                </Link>
              }
            />
          )}
          <div className="flex flex-col gap-4">
            {(candidates ?? []).map((candidate, i) => (
              <CandidateCard
                key={candidate.claims[0]?.id ?? i}
                candidate={candidate}
                existingTypes={events?.map((e) => e.event_type) ?? []}
                onCreated={afterCreate}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function EventCard({ event }: { event: EventItem }) {
  const when = event.occurred_at ?? event.created_at;
  return (
    <Link
      href={`/events/${event.id}`}
      className="flex flex-col gap-1.5 rounded-lg border border-border bg-surface p-4 transition-colors hover:bg-surface-raised"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-medium text-pretty text-foreground">{event.title}</span>
        <div className="flex shrink-0 items-center gap-2">
          <Badge variant="secondary">{event.event_type}</Badge>
          <ConfidenceBadge state={event.knowledge_state} confidence={event.confidence} />
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-3 font-mono text-[11px] text-text-tertiary">
        <span className="flex items-center gap-1">
          <CalendarClock aria-hidden className="h-3 w-3" />
          {new Date(when).toLocaleString("tr-TR")}
          {/* Olayın ne zaman OLDUĞU ile ne zaman KAYDEDİLDİĞİ ayrı bilgiler; kart hangisini
              gösterdiğini söylemezse ikisi birbirine karışır. */}
          {!event.occurred_at && <span className="ml-1 not-italic">· kayıt tarihi</span>}
        </span>
        {event.location && (
          <span className="flex items-center gap-1">
            <MapPin aria-hidden className="h-3 w-3" />
            {event.location}
          </span>
        )}
      </div>
    </Link>
  );
}

/** Bir doğrulama kümesini Event'e çevirir. Kümenin tamamını almak zorunlu değil:
 * bağlantı zinciri iki ayrı olayı birleştirmiş olabilir (gerçek veride oldu), o yüzden
 * her claim tek tek çıkarılabiliyor ve seçim sayısı butonun üstünde yazıyor. */
function CandidateCard({
  candidate,
  existingTypes,
  onCreated,
}: {
  candidate: EventCandidate;
  existingTypes: string[];
  onCreated: () => void;
}) {
  const toast = useToast();
  const [selected, setSelected] = useState<string[]>(candidate.claims.map((c) => c.id));
  const [title, setTitle] = useState("");
  const [eventType, setEventType] = useState("");
  const [occurredAt, setOccurredAt] = useState("");
  const [busy, setBusy] = useState(false);
  const idBase = `candidate-${candidate.claims[0]?.id ?? "x"}`;

  const entityNames = candidate.entities.map((e) => e.name);

  function toggle(id: string, on: boolean) {
    setSelected((prev) => (on ? [...new Set([...prev, id])] : prev.filter((c) => c !== id)));
  }

  async function create() {
    if (!title.trim() || !eventType.trim() || selected.length === 0) return;
    setBusy(true);
    try {
      const res = await api.events.fromCluster({
        title: title.trim(),
        event_type: eventType.trim(),
        occurred_at: occurredAt ? new Date(occurredAt).toISOString() : null,
        claim_ids: selected,
      });
      toast(
        `"${res.event.title}" kuruldu — ${res.linked_claims} claim bağlandı` +
          (res.linked_entities.length ? `, ${res.linked_entities.length} entity taşındı` : ""),
        "success"
      );
      onCreated();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Olay kurulamadı", "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-surface p-4">
      <div className="flex flex-wrap items-center gap-2 text-xs text-text-secondary">
        <Badge variant="outline">{candidate.claim_count} claim</Badge>
        {/* Q6: ham kaynak sayısı ile bağımsız kaynak sayısı ayrı. İkisi eşit değilse
            farkı söylemek zorundayız — "4 site bildirdi"yi "4 bağımsız kaynak doğruladı"
            diye okumak Faz 17'nin engellemek için kurulduğu hatanın ta kendisi. */}
        <Badge variant="outline">
          {candidate.independent_source_count} bağımsız kaynak
          {candidate.source_count !== candidate.independent_source_count &&
            ` (${candidate.source_count} kayıt)`}
        </Badge>
        {entityNames.length > 0 && <span>İlgili: {entityNames.join(", ")}</span>}
      </div>

      <ul className="flex flex-col gap-2">
        {candidate.claims.map((claim) => {
          const checked = selected.includes(claim.id);
          return (
            <li
              key={claim.id}
              className="flex items-start gap-3 rounded-lg border border-border bg-surface-raised/40 p-3"
            >
              {/* `Checkbox` erişilebilir ismini `aria-label`'dan alıyor; hepsine aynı ismi
                  vermek ekran okuyucuda "hangi satırdayım" bilgisini yok ederdi — isim
                  claim'in kendisi. */}
              <Checkbox
                checked={checked}
                onCheckedChange={(on) => toggle(claim.id, Boolean(on))}
                aria-label={`Olaya dahil et: ${excerpt(claim.text)}`}
              />
              <div className="min-w-0 flex-1">
                <p className="text-sm text-pretty text-foreground">{excerpt(claim.text)}</p>
                <div className="mt-1.5 flex flex-wrap items-center gap-2">
                  <ConfidenceBadge state={claim.knowledge_state} confidence={claim.confidence} />
                  {claim.source_name && (
                    <span className="text-[11px] text-text-tertiary">{claim.source_name}</span>
                  )}
                  {claim.about_entity_name && (
                    <span className="text-[11px] text-text-tertiary">
                      şu an: {claim.about_entity_name}
                    </span>
                  )}
                </div>
              </div>
            </li>
          );
        })}
      </ul>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-[2fr_1fr_1fr]">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={`${idBase}-title`}>Olay başlığı</Label>
          <Input
            id={`${idBase}-title`}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="ör. GPT-6 Astra lansmanı"
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={`${idBase}-type`}>Tür</Label>
          <TypeCombo
            id={`${idBase}-type`}
            value={eventType}
            onChange={setEventType}
            suggestions={[...EVENT_TYPE_SUGGESTIONS, ...existingTypes]}
            placeholder="ör. lansman"
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor={`${idBase}-when`}>Ne zaman oldu (opsiyonel)</Label>
          <Input
            id={`${idBase}-when`}
            type="date"
            value={occurredAt}
            onChange={(e) => setOccurredAt(e.target.value)}
          />
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-text-tertiary">
          {selected.length} claim bu olaya bağlanacak.
          {candidate.entities.length > 0 && (
            <>
              {" "}
              Claim&apos;lerin entity bağı silinmez, olaya taşınır:{" "}
              <span className="text-text-secondary">{entityNames.join(", ")}</span> olaya karışan taraf
              olarak bağlanır.
            </>
          )}
        </p>
        <Button onClick={create} disabled={busy || !title.trim() || !eventType.trim() || selected.length === 0}>
          {busy ? "Kuruluyor…" : "Olayı kur"}
        </Button>
      </div>
    </div>
  );
}

function NewEventDialog({ onCreated, existingTypes }: { onCreated: () => void; existingTypes: string[] }) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [eventType, setEventType] = useState("");
  const [occurredAt, setOccurredAt] = useState("");
  const [location, setLocation] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (!title.trim() || !eventType.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.events.create({
        title: title.trim(),
        event_type: eventType.trim(),
        occurred_at: occurredAt ? new Date(occurredAt).toISOString() : null,
        location: location.trim() || null,
      });
      toast(`"${title.trim()}" eklendi`, "success");
      setTitle("");
      setOccurredAt("");
      setLocation("");
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
            Yeni Olay
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Yeni olay ekle</DialogTitle>
          <DialogDescription>
            Grafa yeni bir olay ekler. Claim&apos;ler sonradan bağlanabilir; olayın confidence&apos;ı
            bağlanan claim&apos;lerden türetilir.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="event-title">Başlık</Label>
            <Input
              id="event-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="ör. ChatGPT kesintisi"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="event-type">Tür</Label>
            <TypeCombo
              id="event-type"
              value={eventType}
              onChange={setEventType}
              suggestions={[...EVENT_TYPE_SUGGESTIONS, ...existingTypes]}
              placeholder="ör. kesinti, lansman"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="event-when">Ne zaman oldu (opsiyonel)</Label>
            <Input
              id="event-when"
              type="date"
              value={occurredAt}
              onChange={(e) => setOccurredAt(e.target.value)}
            />
            <p className="text-xs text-text-tertiary">
              Boş bırakılırsa olay zaman çizgisinde kayıt tarihiyle durur.
            </p>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="event-location">Yer (opsiyonel)</Label>
            <Input
              id="event-location"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="ör. San Francisco"
            />
          </div>
          {error && <p className="text-sm text-priority-critical-text">{error}</p>}
        </div>
        <DialogFooter>
          <Button onClick={submit} disabled={submitting || !title.trim() || !eventType.trim()}>
            {submitting ? "Ekleniyor…" : "Ekle"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
