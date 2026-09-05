"use client";

import { useState } from "react";
import Link from "next/link";
import { Plus } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorState, EmptyState } from "@/components/ui/state";
import { SkeletonDetail } from "@/components/ui/skeleton";
import { ConfidenceBadge } from "@/components/provenance/confidence";
import { WhyMattersDisclosure } from "@/components/provenance/why-matters-disclosure";
import { NewClaimDialog } from "@/components/forms/claim-form";
import { EvidenceLinkDialog } from "@/components/forms/evidence-link-dialog";
import { SearchablePicker } from "@/components/forms/searchable-picker";
import { Dialog, DialogContent, DialogFooter, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast";

export function EventDetail({ eventId }: { eventId: string }) {
  const { data: event, error: eventError, loading: eventLoading } = useApi(() => api.events.get(eventId), [eventId]);
  const { data: recall, error: recallError, loading: recallLoading, reload: reloadRecall } = useApi(
    () => api.events.recall(eventId),
    [eventId]
  );

  if (eventLoading || recallLoading) return <SkeletonDetail />;
  if (eventError) return <ErrorState message={eventError.message} />;
  if (recallError) return <ErrorState message={recallError.message} />;
  if (!event || !recall) return null;

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="font-display text-[2rem] font-semibold tracking-tight text-balance text-foreground">{event.title}</h1>
            <Badge variant="secondary">{event.event_type}</Badge>
          </div>
          <div className="mt-1 flex items-center gap-3">
            <ConfidenceBadge state={event.knowledge_state} confidence={event.confidence} />
            {event.location && <span className="text-sm text-text-secondary">{event.location}</span>}
          </div>
          {event.occurred_at && (
            <p className="mt-1 font-mono text-xs text-text-tertiary">
              {new Date(event.occurred_at).toLocaleString("tr-TR")}
            </p>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <NewClaimDialog aboutEventId={eventId} relatedClaims={recall.related_claims} onCreated={reloadRecall} />
          <NewLinkSourceDialog eventId={eventId} onLinked={reloadRecall} />
        </div>
      </header>

      <section>
        <h2 className="mb-2 text-sm font-medium uppercase tracking-wide text-text-tertiary">Bildiren Kaynaklar</h2>
        {recall.reported_by.length === 0 ? (
          <EmptyState title="Bu event'i bildiren bir kaynak henüz yok" />
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
          <EmptyState title="Bu event'e henüz entity bağlanmadı" />
        ) : (
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {recall.related_entities.map((entity) => (
              <Link
                key={entity.id}
                href={`/entities/${entity.id}`}
                className="rounded-lg border border-border bg-surface p-3 transition-colors hover:bg-surface-raised"
              >
                <p className="text-sm font-medium text-foreground">{entity.name}</p>
                <p className="text-xs text-text-tertiary">{entity.entity_type}</p>
              </Link>
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-2 text-sm font-medium uppercase tracking-wide text-text-tertiary">Claim&apos;ler</h2>
        {recall.related_claims.length === 0 ? (
          <EmptyState title="Bu event hakkında claim yok" />
        ) : (
          <div className="flex flex-col gap-2">
            {recall.related_claims.map((claim) => (
              <div key={claim.id} className="rounded-lg border border-border bg-surface p-3">
                <div className="flex items-start justify-between gap-3">
                  <p className="text-sm text-pretty text-foreground">{claim.text}</p>
                  <ConfidenceBadge state={claim.knowledge_state} confidence={claim.confidence} className="shrink-0" />
                </div>
                <div className="mt-2 flex flex-wrap items-start gap-3">
                  <WhyMattersDisclosure claimId={claim.id} />
                  <EvidenceLinkDialog claimId={claim.id} onLinked={reloadRecall} />
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-2 text-sm font-medium uppercase tracking-wide text-text-tertiary">Investigation&apos;lar</h2>
        {recall.related_investigations.length === 0 ? (
          <EmptyState title="Bu event bir investigation'a dahil değil" />
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

function NewLinkSourceDialog({ eventId, onLinked }: { eventId: string; onLinked: () => void }) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const { data: sources } = useApi(() => api.sources.list(), [open]);
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
          <SearchablePicker items={items} value={sourceId} onChange={setSourceId} placeholder="Kaynak ara…" />
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
