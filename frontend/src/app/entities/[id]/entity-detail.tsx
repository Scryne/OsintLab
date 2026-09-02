"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Bell, BellOff, Calendar } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import type { Claim, Source } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/state";
import { ConfidenceBadge, ConfidenceRail } from "@/components/provenance/confidence";
import { ProvenanceBlock } from "@/components/provenance/provenance-label";
import { WhyMattersDisclosure } from "@/components/provenance/why-matters-disclosure";
import type { KnowledgeState } from "@/lib/types";

export function EntityDetail({ entityId }: { entityId: string }) {
  const { data: entity, error: entityError, loading: entityLoading } = useApi(
    () => api.entities.get(entityId),
    [entityId]
  );
  const { data: recall, error: recallError, loading: recallLoading } = useApi(
    () => api.entities.recall(entityId),
    [entityId]
  );

  // recall.related_claims'de source_id/updated_at yok (recall.py bilerek dar bir alan
  // seti döndürüyor) — Sources/Recent Changes panelleri için her claim'i tekil çekiyoruz.
  const [fullClaims, setFullClaims] = useState<Claim[] | null>(null);
  const [sources, setSources] = useState<Record<string, Source>>({});

  useEffect(() => {
    if (!recall) return;
    let cancelled = false;
    Promise.all(recall.related_claims.map((c) => api.claims.get(c.id))).then(async (claims) => {
      if (cancelled) return;
      setFullClaims(claims);
      const uniqueSourceIds = Array.from(new Set(claims.map((c) => c.source_id)));
      const resolved = await Promise.all(uniqueSourceIds.map((sid) => api.sources.get(sid)));
      if (cancelled) return;
      setSources(Object.fromEntries(resolved.map((s) => [s.id, s])));
    });
    return () => {
      cancelled = true;
    };
  }, [recall]);

  const [monitor, setMonitor] = useState<{ id: string } | null | undefined>(undefined);
  useEffect(() => {
    let cancelled = false;
    api.monitors.list(true).then((monitors) => {
      if (cancelled) return;
      setMonitor(monitors.find((m) => m.target_type === "Entity" && m.target_id === entityId) ?? null);
    });
    return () => {
      cancelled = true;
    };
  }, [entityId]);

  async function toggleMonitor() {
    if (monitor) {
      await api.monitors.delete(monitor.id);
      setMonitor(null);
    } else {
      const created = await api.monitors.create({ target_type: "Entity", target_id: entityId });
      setMonitor(created);
    }
  }

  const [confidenceFilter, setConfidenceFilter] = useState<KnowledgeState | null>(null);

  const timelineItems = useMemo(() => {
    const claims = (fullClaims ?? []).map((c) => ({
      id: c.id,
      kind: "claim" as const,
      title: c.text,
      timestamp: c.created_at,
      knowledge_state: c.knowledge_state,
      confidence: c.confidence,
    }));
    const events = (recall?.related_events ?? []).map((e) => ({
      id: e.id,
      kind: "event" as const,
      title: e.title,
      timestamp: e.created_at,
      knowledge_state: null as KnowledgeState | null,
      confidence: undefined,
    }));
    return [...claims, ...events]
      .filter((item) => !confidenceFilter || item.knowledge_state === confidenceFilter)
      .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
  }, [fullClaims, recall, confidenceFilter]);

  if (entityLoading || recallLoading) return <LoadingState label="Entity yükleniyor…" />;
  if (entityError) return <ErrorState message={entityError.message} />;
  if (recallError) return <ErrorState message={recallError.message} />;
  if (!entity || !recall) return null;

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="font-display text-2xl font-semibold text-foreground">{entity.name}</h1>
            <Badge variant="secondary">{entity.entity_type}</Badge>
          </div>
          {entity.aliases.length > 0 && (
            <p className="mt-1 text-sm text-text-secondary">Alias: {entity.aliases.join(", ")}</p>
          )}
          <p className="mt-1 font-mono text-xs text-text-tertiary">
            {new Date(entity.created_at).toLocaleString("tr-TR")} tarihinde eklendi
          </p>
        </div>
        <Button variant={monitor ? "secondary" : "outline"} size="sm" onClick={toggleMonitor} disabled={monitor === undefined}>
          {monitor ? <Bell className="h-4 w-4" /> : <BellOff className="h-4 w-4" />}
          {monitor ? "İzleniyor" : "İzlemeye al"}
        </Button>
      </header>

      <Tabs defaultValue="timeline">
        <div className="overflow-x-auto">
          <TabsList className="w-max">
            <TabsTrigger value="timeline">Timeline</TabsTrigger>
            <TabsTrigger value="claims">Claim&apos;ler ({recall.related_claims.length})</TabsTrigger>
            <TabsTrigger value="events">Event&apos;ler ({recall.related_events.length})</TabsTrigger>
            <TabsTrigger value="investigations">Investigation&apos;lar ({recall.related_investigations.length})</TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="timeline" className="mt-4">
          <div className="flex flex-col gap-4 sm:flex-row sm:gap-6">
            <div className="shrink-0 border-b border-border pb-3 sm:w-40 sm:border-b-0 sm:border-r sm:pr-4 sm:pb-0">
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-text-tertiary">
                Confidence Spectrum
              </p>
              <ConfidenceRail active={confidenceFilter} onSelect={setConfidenceFilter} />
            </div>
            <div className="min-w-0 flex-1">
              {timelineItems.length === 0 ? (
                <EmptyState title="Timeline boş" description="Bu entity hakkında henüz kayıt yok." />
              ) : (
                <ol className="flex flex-col gap-3">
                  {timelineItems.map((item) => (
                    <li key={`${item.kind}-${item.id}`} className="flex gap-3 rounded-lg border border-border bg-surface p-3">
                      <Calendar aria-hidden className="mt-0.5 h-4 w-4 shrink-0 text-text-tertiary" />
                      <div className="flex min-w-0 flex-col gap-1">
                        <p className="text-sm text-foreground">{item.title}</p>
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-[11px] text-text-tertiary">
                            {new Date(item.timestamp).toLocaleString("tr-TR")}
                          </span>
                          {item.knowledge_state && (
                            <ConfidenceBadge state={item.knowledge_state} confidence={item.confidence} />
                          )}
                          {item.kind === "event" && (
                            <Link href={`/events/${item.id}`} className="text-[11px] text-brand-accent hover:underline">
                              event&apos;e git →
                            </Link>
                          )}
                        </div>
                      </div>
                    </li>
                  ))}
                </ol>
              )}
            </div>
          </div>
        </TabsContent>

        <TabsContent value="claims" className="mt-4">
          {recall.related_claims.length === 0 ? (
            <EmptyState title="Bu entity hakkında claim yok" />
          ) : (
            <div className="flex flex-col gap-3">
              {recall.related_claims.map((claim) => {
                const full = fullClaims?.find((c) => c.id === claim.id);
                const source = full ? sources[full.source_id] : undefined;
                return (
                  <ProvenanceBlock key={claim.id} type="SOURCE_FACT">
                    <div className="flex items-start justify-between gap-3">
                      <p className="text-foreground">{claim.text}</p>
                      <ConfidenceBadge state={claim.knowledge_state} confidence={claim.confidence} className="shrink-0" />
                    </div>
                    {source && (
                      <p className="mt-1 text-xs text-text-tertiary">
                        Kaynak: {source.name}
                        {source.url && (
                          <>
                            {" · "}
                            <a href={source.url} target="_blank" rel="noreferrer" className="text-brand-accent hover:underline">
                              {source.url}
                            </a>
                          </>
                        )}
                      </p>
                    )}
                    <WhyMattersDisclosure claimId={claim.id} />
                  </ProvenanceBlock>
                );
              })}
            </div>
          )}
        </TabsContent>

        <TabsContent value="events" className="mt-4">
          {recall.related_events.length === 0 ? (
            <EmptyState title="Bu entity bir event'e karışmamış" />
          ) : (
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {recall.related_events.map((event) => (
                <Link
                  key={event.id}
                  href={`/events/${event.id}`}
                  className="rounded-lg border border-border bg-surface p-3 transition-colors hover:bg-surface-raised"
                >
                  <p className="text-sm font-medium text-foreground">{event.title}</p>
                  <p className="text-xs text-text-tertiary">{event.event_type}</p>
                </Link>
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="investigations" className="mt-4">
          {recall.related_investigations.length === 0 ? (
            <EmptyState title="Bu entity bir investigation'a dahil değil" />
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
        </TabsContent>
      </Tabs>
    </div>
  );
}
