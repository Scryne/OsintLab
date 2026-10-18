"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Link2, Pencil, Plus, Users, X } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ErrorState, EmptyState } from "@/components/ui/state";
import { SkeletonDetail } from "@/components/ui/skeleton";
import { ConfidenceBadge } from "@/components/provenance/confidence";
import { ConfidenceExplainDisclosure } from "@/components/provenance/confidence-explain";
import { WhyMattersDisclosure } from "@/components/provenance/why-matters-disclosure";
import { NewClaimDialog } from "@/components/forms/claim-form";
import { EvidenceLinkDialog } from "@/components/forms/evidence-link-dialog";
import { SearchablePicker } from "@/components/forms/searchable-picker";
import { TypeCombo } from "@/components/forms/type-combo";
import { ConfirmButton } from "@/components/ui/confirm-button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast";

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

const ROLE_SUGGESTIONS = ["ilgili", "katılımcı", "fail", "mağdur", "tanık", "düzenleyici"];

export function EventDetail({ eventId }: { eventId: string }) {
  const {
    data: event,
    error: eventError,
    loading: eventLoading,
    reload: reloadEvent,
  } = useApi(() => api.events.get(eventId), [eventId]);
  const { data: recall, error: recallError, loading: recallLoading, reload: reloadRecall } = useApi(
    () => api.events.recall(eventId),
    [eventId]
  );

  function reloadAll() {
    reloadEvent();
    reloadRecall();
  }

  if (eventLoading || recallLoading) return <SkeletonDetail />;
  if (eventError) return <ErrorState error={eventError} />;
  if (recallError) return <ErrorState error={recallError} />;
  if (!event || !recall) return null;

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="font-display text-[2rem] font-semibold tracking-tight text-balance text-foreground">{event.title}</h1>
            <Badge variant="secondary">{event.event_type}</Badge>
          </div>
          <div className="mt-1 flex items-center gap-3">
            <ConfidenceBadge state={event.knowledge_state} confidence={event.confidence} />
            {event.location && <span className="text-sm text-text-secondary">{event.location}</span>}
          </div>
          {/* Faz 18: olayın confidence'ı claim'lerinden TÜRETİLİYOR (en iyi desteklenen
              claim'inin skoru). Sayının nereden geldiğini söylemezsek, kullanıcı bunu
              elle girilmiş bir değer sanardı. */}
          <p className="mt-1 text-xs text-text-tertiary">
            {recall.related_claims.length === 0
              ? "Henüz claim bağlı değil — olayın güveni claim'lerinden türetilir."
              : `Güven, bağlı ${recall.related_claims.length} claim'in en iyi destekleneninden türetildi.`}
          </p>
          <p className="mt-1 font-mono text-xs text-text-tertiary">
            {event.occurred_at
              ? `${new Date(event.occurred_at).toLocaleString("tr-TR")} tarihinde oldu`
              : `${new Date(event.created_at).toLocaleString("tr-TR")} tarihinde kaydedildi · olay tarihi girilmedi`}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 lg:shrink-0">
          <NewClaimDialog aboutEventId={eventId} relatedClaims={recall.related_claims} onCreated={reloadAll} />
          <LinkClaimDialog eventId={eventId} onLinked={reloadAll} />
          <LinkEntityDialog eventId={eventId} linked={recall.related_entities.map((e) => e.id)} onLinked={reloadAll} />
          <LinkSourceDialog eventId={eventId} onLinked={reloadAll} />
          <EditEventDialog event={event} onSaved={reloadAll} />
        </div>
      </header>

      <section>
        <h2 className="mb-2 text-sm font-medium uppercase tracking-wide text-text-tertiary">Bildiren Kaynaklar</h2>
        {recall.reported_by.length === 0 ? (
          <EmptyState
              title="Bu event'i bildiren bir kaynak henüz yok"
              description="Olayı bildiren kaynağı bağladığında provenance zinciri burada kurulur." />
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {recall.reported_by.map((s) => (
              <Badge key={s.id} variant="outline">
                {s.name} · {s.source_type}
              </Badge>
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-2 text-sm font-medium uppercase tracking-wide text-text-tertiary">İlgili Entity&apos;ler</h2>
        {recall.related_entities.length === 0 ? (
          <EmptyState
              title="Bu event'e henüz entity bağlanmadı"
              description="Olaya karışan kişi ve kurumlar bağlandığında burada listelenir."
              action={<LinkEntityDialog eventId={eventId} linked={[]} onLinked={reloadAll} />} />
        ) : (
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {recall.related_entities.map((entity) => (
              <div
                key={entity.id}
                className="flex items-center justify-between gap-2 rounded-lg border border-border bg-surface p-3 transition-colors hover:bg-surface-raised"
              >
                <Link href={`/entities/${entity.id}`} className="min-w-0">
                  <p className="text-sm font-medium text-foreground">{entity.name}</p>
                  <p className="text-xs text-text-tertiary">{entity.entity_type}</p>
                </Link>
                <ConfirmButton
                  size="icon-xs"
                  variant="ghost"
                  aria-label={`${entity.name} bağını kaldır`}
                  confirmAction="Bağı kaldır"
                  onConfirm={async () => {
                    await api.events.unlinkEntity(eventId, entity.id);
                    reloadAll();
                  }}
                >
                  <X aria-hidden className="h-3 w-3" />
                </ConfirmButton>
              </div>
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-2 text-sm font-medium uppercase tracking-wide text-text-tertiary">Claim&apos;ler</h2>
        {recall.related_claims.length === 0 ? (
          <EmptyState
            title="Bu event hakkında claim yok"
            description="Bu olay hakkında bir iddia kaydettiğinde ya da mevcut bir claim'i bağladığında burada görünür."
            action={<LinkClaimDialog eventId={eventId} onLinked={reloadAll} />} />
        ) : (
          <div className="flex flex-col gap-2">
            {recall.related_claims.map((claim) => (
              <div key={claim.id} className="rounded-lg border border-border bg-surface p-3">
                <div className="flex items-start justify-between gap-3">
                  <p className="text-sm text-pretty text-foreground">{claim.text}</p>
                  <div className="flex shrink-0 items-center gap-2">
                    <ConfidenceBadge state={claim.knowledge_state} confidence={claim.confidence} />
                    {/* Yanlış kümelenmiş bir claim'i çıkarmanın yolu: claim SİLİNMEZ
                        (History Is Immutable), yalnızca olayla bağı kalkar. */}
                    <ConfirmButton
                      size="icon-xs"
                      variant="ghost"
                      aria-label="Bu claim'i olaydan çıkar"
                      confirmAction="Olaydan çıkar"
                      onConfirm={async () => {
                        await api.events.unlinkClaim(eventId, claim.id);
                        reloadAll();
                      }}
                    >
                      <X aria-hidden className="h-3 w-3" />
                    </ConfirmButton>
                  </div>
                </div>
                <div className="mt-2 flex flex-wrap items-start gap-3">
                  <WhyMattersDisclosure claimId={claim.id} />
                  <ConfidenceExplainDisclosure claimId={claim.id} />
                  <EvidenceLinkDialog claimId={claim.id} onLinked={reloadAll} />
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-2 text-sm font-medium uppercase tracking-wide text-text-tertiary">Investigation&apos;lar</h2>
        {recall.related_investigations.length === 0 ? (
          <EmptyState
              title="Bu event bir investigation'a dahil değil"
              description="Bir araştırmanın kapsamına eklendiğinde o araştırma burada görünür." />
        ) : (
          <div className="flex flex-col gap-2">
            {recall.related_investigations.map((inv) => (
              <Link
                key={inv.id}
                href={`/investigations/${inv.id}`}
                className="flex items-center justify-between rounded-lg border border-border bg-surface p-3 transition-colors hover:bg-surface-raised"
              >
                <span className="text-sm text-foreground">{inv.title}</span>
                <Badge variant="outline">{inv.status}</Badge>
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

/** Faz 18: mevcut bir claim'i bu olaya bağlar. `ClaimLinkDialog`'un entity karşılığı vardı,
 * event tarafı yoktu — promote sırasında olay seçilemediği için (hiç olay yoktu) her claim
 * entity'ye asılmıştı; onarım yolu buradan geçiyor. */
function LinkClaimDialog({ eventId, onLinked }: { eventId: string; onLinked: () => void }) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  // Kapalı dialog veri çekmez — koşulsuz çekim `/observations`'ta tek açılışta 2336 isteğe
  // yol açmıştı (Frontend Sertleştirme Turu, 2026-09-06).
  const { data: claims } = useApi(() => (open ? api.claims.list() : Promise.resolve([])), [open]);
  const [claimId, setClaimId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const items = useMemo(() => {
    const all = claims ?? [];
    const label = (text: string) => text.split("\n")[0].slice(0, 64);
    const unlinked = all.filter((c) => !c.about_entity_id && !c.about_event_id);
    const others = all.filter(
      (c) => c.about_event_id !== eventId && (c.about_entity_id || c.about_event_id)
    );
    return [
      ...unlinked.map((c) => ({ id: c.id, label: label(c.text), sublabel: "bağlantısız" })),
      ...others.map((c) => ({
        id: c.id,
        label: label(c.text),
        sublabel: c.about_entity_id ? "bir entity'ye bağlı" : "başka bir olaya bağlı",
      })),
    ];
  }, [claims, eventId]);

  async function submit() {
    if (!claimId) return;
    setSubmitting(true);
    try {
      await api.events.linkClaim(eventId, claimId);
      toast("Claim bu olaya bağlandı", "success");
      setClaimId(null);
      setOpen(false);
      onLinked();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Bağlanamadı", "error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => { setOpen(next); if (!next) setClaimId(null); }}>
      <DialogTrigger
        render={
          <Button variant="outline" size="sm">
            <Link2 aria-hidden className="h-4 w-4" />
            Claim bağla
          </Button>
        }
      />
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Claim&apos;i bu olaya bağla</DialogTitle>
          <DialogDescription>
            Claim&apos;in metni değişmez, yalnızca neyle ilgili olduğu düzeltilir. Bir claim aynı
            anda hem bir entity hem bir olay hakkında olamaz — entity bağı varsa yerini olay alır.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="event-link-claim">Claim</Label>
          <SearchablePicker id="event-link-claim" items={items} value={claimId} onChange={setClaimId} placeholder="Claim ara…" />
          <p className="text-xs text-text-tertiary">Bağlantısız claim&apos;ler listenin başında.</p>
        </div>
        <DialogFooter>
          <Button onClick={submit} disabled={submitting || !claimId}>
            {submitting ? "Bağlanıyor…" : "Bağla"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** INVOLVED_IN yazan uç Faz 1'den beri vardı, arayüzü yoktu. Rol serbest metin: "fail" ile
 * "mağdur" arasındaki farkı sistem bilemez, araştırmacı bilir. */
function LinkEntityDialog({
  eventId,
  linked,
  onLinked,
}: {
  eventId: string;
  linked: string[];
  onLinked: () => void;
}) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const { data: entities } = useApi(() => (open ? api.entities.list() : Promise.resolve([])), [open]);
  const [entityId, setEntityId] = useState<string | null>(null);
  const [role, setRole] = useState("ilgili");
  const [submitting, setSubmitting] = useState(false);

  const items = (entities ?? [])
    .filter((e) => !linked.includes(e.id))
    .map((e) => ({ id: e.id, label: e.name, sublabel: e.entity_type }));

  async function submit() {
    if (!entityId || !role.trim()) return;
    setSubmitting(true);
    try {
      await api.events.linkEntity(eventId, entityId, role.trim());
      toast("Entity olaya bağlandı", "success");
      setEntityId(null);
      setOpen(false);
      onLinked();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Bağlanamadı", "error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => { setOpen(next); if (!next) setEntityId(null); }}>
      <DialogTrigger
        render={
          <Button variant="outline" size="sm">
            <Users aria-hidden className="h-4 w-4" />
            Entity bağla
          </Button>
        }
      />
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Olaya karışan entity&apos;yi bağla</DialogTitle>
          <DialogDescription>
            Bu olaya karışan kişi/kurumu işaretler. Rolü sen verirsin — sistem &quot;fail&quot; ile
            &quot;mağdur&quot;u ayırt edemez.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="event-link-entity">Entity</Label>
            <SearchablePicker
              id="event-link-entity"
              items={items}
              value={entityId}
              onChange={setEntityId}
              placeholder="Entity ara…"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="event-link-role">Rol</Label>
            <TypeCombo
              id="event-link-role"
              value={role}
              onChange={setRole}
              suggestions={ROLE_SUGGESTIONS}
              placeholder="ör. fail, mağdur"
            />
          </div>
        </div>
        <DialogFooter>
          <Button onClick={submit} disabled={submitting || !entityId || !role.trim()}>
            {submitting ? "Bağlanıyor…" : "Bağla"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Bir olayın ne zaman olduğu genellikle ilk claim'den SONRA netleşir; düzeltme yolu
 * olmasaydı adaydan kurulan her olay kayıt tarihiyle donup kalırdı. */
function EditEventDialog({
  event,
  onSaved,
}: {
  event: { id: string; title: string; event_type: string; occurred_at: string | null; location: string | null };
  onSaved: () => void;
}) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState(event.title);
  const [eventType, setEventType] = useState(event.event_type);
  const [occurredAt, setOccurredAt] = useState(event.occurred_at ? event.occurred_at.slice(0, 10) : "");
  const [location, setLocation] = useState(event.location ?? "");
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    if (!title.trim() || !eventType.trim()) return;
    setSubmitting(true);
    try {
      await api.events.update(event.id, {
        title: title.trim(),
        event_type: eventType.trim(),
        occurred_at: occurredAt ? new Date(occurredAt).toISOString() : null,
        location: location.trim() || null,
      });
      toast("Olay güncellendi", "success");
      setOpen(false);
      onSaved();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Kaydedilemedi", "error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button variant="outline" size="sm">
            <Pencil aria-hidden className="h-4 w-4" />
            Düzenle
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Olayı düzenle</DialogTitle>
          <DialogDescription>
            Olayın sınıflandırması düzeltilir; bağlı claim&apos;lerin metnine dokunulmaz.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="edit-event-title">Başlık</Label>
            <Input id="edit-event-title" value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="edit-event-type">Tür</Label>
            <TypeCombo
              id="edit-event-type"
              value={eventType}
              onChange={setEventType}
              suggestions={EVENT_TYPE_SUGGESTIONS}
              placeholder="ör. lansman"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="edit-event-when">Ne zaman oldu</Label>
            <Input
              id="edit-event-when"
              type="date"
              value={occurredAt}
              onChange={(e) => setOccurredAt(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="edit-event-location">Yer</Label>
            <Input id="edit-event-location" value={location} onChange={(e) => setLocation(e.target.value)} />
          </div>
        </div>
        <DialogFooter>
          <Button onClick={submit} disabled={submitting || !title.trim() || !eventType.trim()}>
            {submitting ? "Kaydediliyor…" : "Kaydet"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function LinkSourceDialog({ eventId, onLinked }: { eventId: string; onLinked: () => void }) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const { data: sources } = useApi(() => (open ? api.sources.list() : Promise.resolve([])), [open]);
  const [sourceId, setSourceId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const items = (sources ?? []).map((s) => ({ id: s.id, label: s.name, sublabel: s.source_type }));

  async function submit() {
    if (!sourceId) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.events.linkSource(eventId, sourceId);
      toast("Kaynak bağlandı", "success");
      setSourceId(null);
      setOpen(false);
      onLinked();
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
          <Button variant="outline" size="sm">
            <Plus aria-hidden className="h-4 w-4" />
            Kaynak Ekle
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Bu event&apos;i bildiren kaynağı bağla</DialogTitle>
          <DialogDescription>Bu event&apos;i bildiren kaynağı işaretler; olayın provenance zinciri buradan kurulur.</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <SearchablePicker items={items} value={sourceId} onChange={setSourceId} placeholder="Kaynak ara…" aria-label="Bildiren kaynak" />
          {error && <p className="text-sm text-priority-critical-text">{error}</p>}
        </div>
        <DialogFooter>
          <Button onClick={submit} disabled={submitting || !sourceId}>
            {submitting ? "Bağlanıyor…" : "Bağla"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
