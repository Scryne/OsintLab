"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Search, Users, Calendar, FolderSearch, Radio } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { Input } from "@/components/ui/input";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/state";
import { ConfidenceBadge } from "@/components/provenance/confidence";
import { PriorityBadge } from "@/components/provenance/priority";

export default function MainWorkspace() {
  const { data: entities } = useApi(() => api.entities.list(), []);
  const { data: events } = useApi(() => api.events.list(), []);
  const { data: investigations } = useApi(() => api.investigations.list(), []);
  const { data: sources } = useApi(() => api.sources.list(), []);
  const { data: claims, loading: claimsLoading, error: claimsError } = useApi(() => api.claims.list(), []);
  const { data: inbox, loading: inboxLoading, error: inboxError } = useApi(
    () => api.inbox.list({ min_priority: "MEDIUM" }),
    []
  );

  const [query, setQuery] = useState("");
  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return { entities: [], events: [] };
    return {
      entities: (entities ?? []).filter((e) => e.name.toLowerCase().includes(q)).slice(0, 6),
      events: (events ?? []).filter((e) => e.title.toLowerCase().includes(q)).slice(0, 6),
    };
  }, [query, entities, events]);

  const recentClaims = useMemo(
    () => [...(claims ?? [])].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()).slice(0, 8),
    [claims]
  );

  const topInbox = useMemo(
    () =>
      [...(inbox ?? [])]
        .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
        .slice(0, 5),
    [inbox]
  );

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-8">
      <section>
        <h1 className="font-display text-2xl font-semibold text-foreground">Ana Çalışma Alanı</h1>
        <p className="mt-1 text-sm text-text-secondary">
          Bilinen entity ve event&apos;lerde ara — sonuçlar Knowledge Graph&apos;a dayanır.
        </p>
        <div className="relative mt-4">
          <Search aria-hidden className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-tertiary" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Bir kişi, kurum, lokasyon ya da event ara…"
            className="h-11 pl-9 text-base"
          />
        </div>
        {query.trim() && (
          <div className="mt-2 flex flex-col gap-1 rounded-lg border border-border bg-surface p-2">
            {results.entities.length === 0 && results.events.length === 0 && (
              <p className="p-2 text-sm text-text-tertiary">Eşleşme yok.</p>
            )}
            {results.entities.map((e) => (
              <Link key={e.id} href={`/entities/${e.id}`} className="rounded-md px-2 py-1.5 text-sm hover:bg-surface-raised">
                <Users className="mr-2 inline h-3.5 w-3.5 text-text-tertiary" />
                {e.name} <span className="text-xs text-text-tertiary">· {e.entity_type}</span>
              </Link>
            ))}
            {results.events.map((e) => (
              <Link key={e.id} href={`/events/${e.id}`} className="rounded-md px-2 py-1.5 text-sm hover:bg-surface-raised">
                <Calendar className="mr-2 inline h-3.5 w-3.5 text-text-tertiary" />
                {e.title}
              </Link>
            ))}
          </div>
        )}
      </section>

      <section className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard icon={Users} label="Entity" value={entities?.length} href="/entities" />
        <StatCard icon={Calendar} label="Event" value={events?.length} />
        <StatCard icon={FolderSearch} label="Investigation" value={investigations?.length} href="/investigations" />
        <StatCard icon={Radio} label="Source" value={sources?.length} />
      </section>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <section>
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-sm font-medium uppercase tracking-wide text-text-tertiary">Priority Intelligence</h2>
            <Link href="/inbox" className="text-xs text-brand-accent hover:underline">
              Inbox&apos;a git →
            </Link>
          </div>
          <div className="glass-panel rounded-lg p-3">
            {inboxLoading && <LoadingState label="Inbox yükleniyor…" />}
            {inboxError && <ErrorState message={inboxError.message} />}
            {!inboxLoading && !inboxError && topInbox.length === 0 && (
              <EmptyState title="MEDIUM+ öncelikli bekleyen bir şey yok" />
            )}
            <div className="flex flex-col gap-2">
              {topInbox.map((item) => (
                <div key={item.id} className="flex items-center justify-between gap-2 rounded-md bg-surface/60 px-2.5 py-2">
                  <div className="min-w-0">
                    <p className="truncate text-sm text-foreground">{item.title}</p>
                    <p className="text-[11px] text-text-tertiary">{item.item_type}</p>
                  </div>
                  <PriorityBadge priority={item.priority} className="shrink-0" />
                </div>
              ))}
            </div>
          </div>
        </section>

        <section>
          <h2 className="mb-2 text-sm font-medium uppercase tracking-wide text-text-tertiary">Son Değişiklikler</h2>
          {claimsLoading && <LoadingState label="Timeline yükleniyor…" />}
          {claimsError && <ErrorState message={claimsError.message} />}
          {!claimsLoading && !claimsError && recentClaims.length === 0 && <EmptyState title="Henüz claim yok" />}
          <div className="flex flex-col gap-2">
            {recentClaims.map((claim) => (
              <div key={claim.id} className="flex items-start justify-between gap-2 rounded-lg border border-border bg-surface p-2.5">
                <p className="truncate text-sm text-foreground">{claim.text}</p>
                <ConfidenceBadge state={claim.knowledge_state} confidence={claim.confidence} className="shrink-0" />
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  href,
}: {
  icon: typeof Users;
  label: string;
  value: number | undefined;
  href?: string;
}) {
  const content = (
    <div className="flex items-center gap-3 rounded-lg border border-border bg-surface p-3">
      <Icon aria-hidden className="h-5 w-5 text-brand-accent" />
      <div>
        <p className="font-mono text-lg font-semibold text-foreground">{value ?? "–"}</p>
        <p className="text-xs text-text-tertiary">{label}</p>
      </div>
    </div>
  );
  return href ? (
    <Link href={href} className="transition-opacity hover:opacity-80">
      {content}
    </Link>
  ) : (
    content
  );
}
