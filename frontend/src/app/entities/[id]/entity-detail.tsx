"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Bell, BellOff, Calendar, GitBranchPlus, Plus, X } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import type { Claim, SameAsCandidate, Source } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/state";
import { ConfidenceBadge, ConfidenceRail } from "@/components/provenance/confidence";
import { ProvenanceBlock } from "@/components/provenance/provenance-label";
import { WhyMattersDisclosure } from "@/components/provenance/why-matters-disclosure";
import type { KnowledgeState } from "@/lib/types";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { SearchablePicker } from "@/components/forms/searchable-picker";
import { NewClaimDialog } from "@/components/forms/claim-form";
import { EvidenceLinkDialog } from "@/components/forms/evidence-link-dialog";
import { useToast } from "@/components/ui/toast";
import { ConfirmButton } from "@/components/ui/confirm-button";

export function EntityDetail({ entityId }: { entityId: string }) {
  const toast = useToast();
  const { data: entity, error: entityError, loading: entityLoading } = useApi(
    () => api.entities.get(entityId),
    [entityId]
  );
  const { data: recall, error: recallError, loading: recallLoading, reload: reloadRecall } = useApi(
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

  const { data: relations, reload: reloadRelations } = useApi(() => api.entities.listRelations(entityId), [entityId]);
  const { data: sameAsCandidates, reload: reloadSameAs } = useApi(
    () => api.entities.sameAsCandidates(entityId),
    [entityId]
  );

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
            <h1 className="font-display text-[2rem] font-semibold tracking-tight text-foreground">{entity.name}</h1>
            <Badge variant="secondary">{entity.entity_type}</Badge>
          </div>
          {entity.aliases.length > 0 && (
            <p className="mt-1 text-sm text-text-secondary">Alias: {entity.aliases.join(", ")}</p>
          )}
          <p className="mt-1 font-mono text-xs text-text-tertiary">
            {new Date(entity.created_at).toLocaleString("tr-TR")} tarihinde eklendi
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <NewClaimDialog
            aboutEntityId={entityId}
            relatedClaims={recall.related_claims}
            onCreated={reloadRecall}
          />
          <NewRelationDialog entityId={entityId} onCreated={reloadRelations} />
          <Button variant={monitor ? "secondary" : "outline"} size="sm" onClick={toggleMonitor} disabled={monitor === undefined}>
            {monitor ? <Bell className="h-4 w-4" /> : <BellOff className="h-4 w-4" />}
            {monitor ? "İzleniyor" : "İzlemeye al"}
          </Button>
        </div>
      </header>

      <Tabs defaultValue="timeline">
        <div className="overflow-x-auto">
          <TabsList className="w-max">
            <TabsTrigger value="timeline">Timeline</TabsTrigger>
            <TabsTrigger value="claims">Claim&apos;ler ({recall.related_claims.length})</TabsTrigger>
            <TabsTrigger value="events">Event&apos;ler ({recall.related_events.length})</TabsTrigger>
            <TabsTrigger value="investigations">Investigation&apos;lar ({recall.related_investigations.length})</TabsTrigger>
            <TabsTrigger value="relations">İlişkiler ({relations?.length ?? 0})</TabsTrigger>
            <TabsTrigger value="same-as">Olası Eşleşmeler ({sameAsCandidates?.length ?? 0})</TabsTrigger>
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
                            <Link href={`/events/${item.id}`} className="text-[11px] text-text-secondary underline decoration-white/20 underline-offset-2 hover:text-foreground hover:decoration-white/50">
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
                            <a href={source.url} target="_blank" rel="noreferrer" className="text-text-secondary underline decoration-white/20 underline-offset-2 hover:text-foreground hover:decoration-white/50">
                              {source.url}
                            </a>
                          </>
                        )}
                      </p>
                    )}
                    <div className="flex flex-wrap items-start gap-3">
                      <WhyMattersDisclosure claimId={claim.id} />
                      <EvidenceLinkDialog claimId={claim.id} onLinked={reloadRecall} />
                    </div>
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

        <TabsContent value="relations" className="mt-4">
          {!relations || relations.length === 0 ? (
            <EmptyState title="Henüz kayıtlı bir ilişki yok" description="Yukarıdaki 'İlişki Ekle' butonuyla ilk ilişkiyi kur." />
          ) : (
            <div className="flex flex-col gap-2">
              {relations.map((r) => (
                <div
                  key={`${r.direction}-${r.entity_id}-${r.relation_type}`}
                  className="flex items-center justify-between gap-3 rounded-lg border border-border bg-surface p-3"
                >
                  <div className="flex min-w-0 items-center gap-2 text-sm">
                    <span className="text-text-tertiary">{r.direction === "OUTGOING" ? "→" : "←"}</span>
                    <Badge variant="secondary">{r.relation_type}</Badge>
                    <Link href={`/entities/${r.entity_id}`} className="truncate text-foreground hover:underline">
                      {r.name}
                    </Link>
                  </div>
                  <ConfirmButton
                    size="icon-sm"
                    variant="ghost"
                    aria-label="İlişkiyi kaldır"
                    confirmLabel="Kaldırılsın mı?"
                    onConfirm={async () => {
                      const [fromId, toId] =
                        r.direction === "OUTGOING" ? [entityId, r.entity_id] : [r.entity_id, entityId];
                      try {
                        await api.entities.deleteRelation(fromId, toId, r.relation_type);
                        toast("İlişki kaldırıldı", "success");
                        reloadRelations();
                      } catch (err) {
                        toast(err instanceof Error ? err.message : "İlişki kaldırılamadı", "error");
                      }
                    }}
                  >
                    <X aria-hidden className="h-3.5 w-3.5" />
                  </ConfirmButton>
                </div>
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="same-as" className="mt-4">
          <SameAsTab entityId={entityId} candidates={sameAsCandidates ?? []} onChanged={reloadSameAs} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function NewRelationDialog({ entityId, onCreated }: { entityId: string; onCreated: () => void }) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const { data: entities } = useApi(() => api.entities.list(), [open]);
  const [targetId, setTargetId] = useState<string | null>(null);
  const [relationType, setRelationType] = useState("");
  const [confidence, setConfidence] = useState("0.5");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const items = (entities ?? [])
    .filter((e) => e.id !== entityId)
    .map((e) => ({ id: e.id, label: e.name, sublabel: e.entity_type }));

  async function submit() {
    if (!targetId || !relationType.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.entities.createRelation(entityId, {
        to_entity_id: targetId,
        relation_type: relationType.trim(),
        confidence: Number(confidence),
      });
      toast("İlişki eklendi", "success");
      setTargetId(null);
      setRelationType("");
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
          <Button variant="outline" size="sm">
            <GitBranchPlus aria-hidden className="h-4 w-4" />
            İlişki Ekle
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Entity ilişkisi ekle</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label>Hedef entity</Label>
            <SearchablePicker items={items} value={targetId} onChange={setTargetId} placeholder="Entity ara…" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="relation-type">İlişki türü</Label>
            <Input
              id="relation-type"
              value={relationType}
              onChange={(e) => setRelationType(e.target.value)}
              placeholder="ör. çalışıyor, sahibi, ortak"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="relation-confidence">Confidence (0–1)</Label>
            <Input
              id="relation-confidence"
              type="number"
              min={0}
              max={1}
              step={0.05}
              value={confidence}
              onChange={(e) => setConfidence(e.target.value)}
            />
          </div>
          {error && <p className="text-sm text-priority-critical">{error}</p>}
        </div>
        <DialogFooter>
          <Button onClick={submit} disabled={submitting || !targetId || !relationType.trim()}>
            {submitting ? "Ekleniyor…" : "Ekle"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function SameAsTab({
  entityId,
  candidates,
  onChanged,
}: {
  entityId: string;
  candidates: SameAsCandidate[];
  onChanged: () => void;
}) {
  const toast = useToast();
  const { data: pending, reload: reloadPending } = useApi(() => api.entities.pendingSameAs(), [entityId]);
  const [busyId, setBusyId] = useState<string | null>(null);

  const pendingForThisEntity = (pending ?? []).filter(
    (p) => p.entity_a_id === entityId || p.entity_b_id === entityId
  );

  async function suggest(candidateId: string) {
    setBusyId(candidateId);
    try {
      await api.entities.suggestSameAs(entityId, candidateId);
      toast("Öneri kuyruğa eklendi", "success");
      onChanged();
      reloadPending();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Öneri eklenemedi", "error");
    } finally {
      setBusyId(null);
    }
  }

  async function resolve(fromId: string, toId: string, action: "confirm" | "reject") {
    setBusyId(fromId + toId);
    try {
      if (action === "confirm") await api.entities.confirmSameAs(fromId, toId);
      else await api.entities.rejectSameAs(fromId, toId);
      toast(action === "confirm" ? "Eşleşme onaylandı" : "Eşleşme reddedildi", action === "confirm" ? "success" : "default");
      reloadPending();
    } catch (err) {
      toast(err instanceof Error ? err.message : "İşlem başarısız", "error");
    } finally {
      setBusyId(null);
    }
  }

  const suggestedIds = new Set(
    pendingForThisEntity.flatMap((p) => [p.entity_a_id, p.entity_b_id])
  );

  return (
    <div className="flex flex-col gap-6">
      {pendingForThisEntity.length > 0 && (
        <div>
          <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-text-tertiary">Onay bekleyen</h3>
          <div className="flex flex-col gap-2">
            {pendingForThisEntity.map((p) => {
              const otherName = p.entity_a_id === entityId ? p.entity_b_name : p.entity_a_name;
              return (
                <div
                  key={`${p.entity_a_id}-${p.entity_b_id}`}
                  className="flex items-center justify-between gap-3 rounded-lg border border-border bg-surface p-3"
                >
                  <div className="text-sm">
                    <span className="text-foreground">{otherName}</span>{" "}
                    <span className="font-mono text-xs tabular-nums text-text-tertiary">%{Math.round(p.confidence * 100)}</span>
                  </div>
                  <div className="flex shrink-0 items-center gap-1.5">
                    <ConfirmButton
                      size="sm"
                      variant="secondary"
                      confirmLabel="Birleştir?"
                      onConfirm={() => resolve(p.entity_a_id, p.entity_b_id, "confirm")}
                    >
                      Confirm
                    </ConfirmButton>
                    <Button
                      size="sm"
                      variant="destructive"
                      disabled={busyId === p.entity_a_id + p.entity_b_id}
                      onClick={() => resolve(p.entity_a_id, p.entity_b_id, "reject")}
                    >
                      Reject
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div>
        <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-text-tertiary">Olası eşleşme adayları</h3>
        {candidates.length === 0 ? (
          <EmptyState title="Aday bulunamadı" description="İsim/alias benzerliğine göre otomatik hesaplanır." />
        ) : (
          <div className="flex flex-col gap-2">
            {candidates.map((c) => (
              <div key={c.entity_id} className="flex items-center justify-between gap-3 rounded-lg border border-border bg-surface p-3">
                <div className="text-sm">
                  <Link href={`/entities/${c.entity_id}`} className="text-foreground hover:underline">
                    {c.name}
                  </Link>{" "}
                  <span className="font-mono text-xs tabular-nums text-text-tertiary">%{Math.round(c.score * 100)} benzerlik</span>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={busyId === c.entity_id || suggestedIds.has(c.entity_id)}
                  onClick={() => suggest(c.entity_id)}
                >
                  <Plus aria-hidden className="h-3.5 w-3.5" />
                  {suggestedIds.has(c.entity_id) ? "Önerildi" : "Öner"}
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
