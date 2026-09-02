"use client";

import Link from "next/link";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { Badge } from "@/components/ui/badge";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/state";
import { ConfidenceBadge } from "@/components/provenance/confidence";

export function EventDetail({ eventId }: { eventId: string }) {
  const { data: event, error: eventError, loading: eventLoading } = useApi(() => api.events.get(eventId), [eventId]);
  const { data: recall, error: recallError, loading: recallLoading } = useApi(
    () => api.events.recall(eventId),
    [eventId]
  );

  if (eventLoading || recallLoading) return <LoadingState label="Event yükleniyor…" />;
  if (eventError) return <ErrorState message={eventError.message} />;
  if (recallError) return <ErrorState message={recallError.message} />;
  if (!event || !recall) return null;

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <header>
        <div className="flex items-center gap-2">
          <h1 className="font-display text-2xl font-semibold text-foreground">{event.title}</h1>
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
      </header>

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
              <div key={claim.id} className="flex items-start justify-between gap-3 rounded-lg border border-border bg-surface p-3">
                <p className="text-sm text-foreground">{claim.text}</p>
                <ConfidenceBadge state={claim.knowledge_state} confidence={claim.confidence} className="shrink-0" />
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
