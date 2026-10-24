"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Search, Users, Calendar, FolderSearch, Radio } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { Input } from "@/components/ui/input";
import { ErrorState, EmptyState } from "@/components/ui/state";
import { Skeleton, SkeletonRows } from "@/components/ui/skeleton";
import { ConfidenceBadge } from "@/components/provenance/confidence";
import { PriorityBadge } from "@/components/provenance/priority";
import { IconChip } from "@/components/ui/icon-chip";
import { WireframeGlobe } from "@/components/ui/wireframe-globe";
import { ExploitedPanel } from "@/components/pivot/exploited-panel";

export default function MainWorkspace() {
  const { data: entities } = useApi(() => api.entities.list(), []);
  const { data: events } = useApi(() => api.events.list(), []);
  const { data: investigations } = useApi(() => api.investigations.list(), []);
  const { data: sources } = useApi(() => api.sources.list(), []);
  const { data: claims, loading: claimsLoading, error: claimsError } = useApi(() => api.claims.list(), []);
  const { data: inbox, loading: inboxLoading, error: inboxError } = useApi(
    // Yalnızca BEKLEYEN öğeler: durum süzgeci yokken zaten işlenmiş (IGNORED/CONFIRMED)
    // öğeler "acil" diye listeleniyor ve "bekleyen acil bir şey yok" hiç görünmüyordu.
    () => api.inbox.list({ min_priority: "MEDIUM", status: "NEW" }),
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
    <div className="relative isolate mx-auto flex max-w-5xl flex-col gap-8 overflow-hidden">
      <WireframeGlobe spin className="pointer-events-none absolute -right-16 -top-20 -z-10 h-64 w-64 text-white/5" />
      <section>
        <h1 className="font-display text-[2rem] font-semibold tracking-tight text-balance text-foreground">Ana Çalışma Alanı</h1>
        <p className="mt-1 text-sm text-text-secondary">
          Bilinen entity ve event&apos;lerde ara — sonuçlar Knowledge Graph&apos;a dayanır.
        </p>
        {/* Uygulamanın birincil kontrolü etiketsizdi — sadece placeholder vardı, o da
            yazmaya başlayınca kayboluyor ve ekran okuyucuya isim vermiyor. Etiket görsel
            olarak gizli ama gerçek: `sr-only` + `htmlFor`. */}
        <div className="glass-panel relative mt-5 rounded-2xl p-1">
          <label htmlFor="workspace-search" className="sr-only">
            Entity ve event ara
          </label>
          <Search aria-hidden className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-text-tertiary" />
          <Input
            id="workspace-search"
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Bir kişi, kurum, lokasyon ya da event ara…"
            className="h-12 border-0 bg-transparent pl-11 text-base shadow-none focus-visible:ring-0"
          />
        </div>
        {/* Sonuçlar anlık geliyor ama gelişi duyurulmuyordu; klavye/ekran okuyucu
            kullanıcısı listeye Tab'layana kadar bir şey bulunduğunu bilmiyordu. */}
        <p aria-live="polite" className="sr-only">
          {query.trim()
            ? `${results.entities.length + results.events.length} sonuç bulundu`
            : ""}
        </p>
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
        <StatCard icon={Calendar} label="Event" value={events?.length} href="/events" />
        <StatCard icon={FolderSearch} label="Investigation" value={investigations?.length} href="/investigations" />
        <StatCard icon={Radio} label="Source" value={sources?.length} href="/sources" />
      </section>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <section>
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-sm font-medium uppercase tracking-wide text-text-tertiary">Priority Intelligence</h2>
            <Link href="/inbox" className="text-xs text-text-secondary underline decoration-white/20 underline-offset-2 hover:text-foreground hover:decoration-white/50">
              Inbox&apos;a git →
            </Link>
          </div>
          <div className="glass-panel rounded-lg p-3">
            {inboxLoading && <SkeletonRows count={3} />}
            {inboxError && <ErrorState error={inboxError} />}
            {!inboxLoading && !inboxError && topInbox.length === 0 && (
              // "Temizlenmiş boşluk" — kullanıcıyı yönlendirmek değil rahatlatmak
              // gerekiyor: burası boşsa acil bir şey yok demektir.
              <EmptyState
                title="Bekleyen acil bir şey yok"
                description="Orta ve üstü öncelikli bir değişiklik olduğunda burada görünür."
              />
            )}
            <div className="flex flex-col gap-2">
              {topInbox.map((item) => (
                <div key={item.id} className="flex items-center justify-between gap-2 rounded-md bg-surface-raised px-2.5 py-2">
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
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-sm font-medium uppercase tracking-wide text-text-tertiary">Son Değişiklikler</h2>
          </div>
          <div className="glass-panel rounded-lg p-3">
            {claimsLoading && <SkeletonRows count={3} />}
            {claimsError && <ErrorState error={claimsError} />}
            {!claimsLoading && !claimsError && recentClaims.length === 0 && <EmptyState
                title="Henüz claim yok"
                description="Bir gözlemi claim'e yükselttiğinde ya da elle claim eklediğinde burada görünür."
              />}
            <div className="flex flex-col gap-2">
              {recentClaims.map((claim) => (
                <div key={claim.id} className="flex items-start justify-between gap-2 rounded-md bg-surface-raised px-2.5 py-2">
                  <p className="line-clamp-2 text-sm text-pretty text-foreground">{claim.text}</p>
                  <ConfidenceBadge state={claim.knowledge_state} confidence={claim.confidence} className="shrink-0" />
                </div>
              ))}
            </div>
          </div>
        </section>
      </div>

      <ExploitedPanel />
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
    <div className="flex items-center gap-3 rounded-2xl border border-border bg-surface p-4 transition-transform">
      <IconChip icon={Icon} size="lg" />
      <div>
        {value === undefined ? (
          <Skeleton className="h-8 w-10" />
        ) : (
          <p className="font-mono text-3xl leading-none font-semibold tracking-tight tabular-nums text-foreground">{value}</p>
        )}
        <p className="mt-1 text-xs text-text-tertiary">{label}</p>
      </div>
    </div>
  );
  return href ? (
    <Link href={href} className="block transition-transform hover:-translate-y-0.5">
      {content}
    </Link>
  ) : (
    content
  );
}
