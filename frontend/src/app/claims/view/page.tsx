"use client";

import { Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Archive, CalendarClock, Database, Network } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { ConfidenceBadge } from "@/components/provenance/confidence";
import { ConfidenceExplainDisclosure } from "@/components/provenance/confidence-explain";
import { WhyMattersDisclosure } from "@/components/provenance/why-matters-disclosure";
import { SelectorChip } from "@/components/pivot/selector-chip";
import { EnrichmentPanel } from "@/components/pivot/enrichment-panel";
import { EmptyState, ErrorState } from "@/components/ui/state";
import { SkeletonDetail } from "@/components/ui/skeleton";

/** Faz 33 — claim ayrıntısı.
 *
 * Claim'in kendi sayfası yoktu: arama, rapor ve seçici sayfası bir claim'e bağlanmak istediğinde
 * gidecek yer yoktu, kullanıcı claim'i ancak bir entity'nin sekmesinde ya da doğrulama ekranında
 * görebiliyordu. Bu sayfa bir claim hakkında bilinen her şeyi tek yerde toplar: kaynağı,
 * öznesi, confidence'ın dökümü, arşiv kaydı ve metninden çıkan seçiciler. */
export default function ClaimViewPage() {
  return (
    <Suspense fallback={<div className="mx-auto max-w-4xl"><SkeletonDetail /></div>}>
      <ClaimView />
    </Suspense>
  );
}

function ClaimView() {
  const id = useSearchParams().get("id") ?? "";
  const { data: claim, error, loading, reload } = useApi(() => api.claims.get(id), [id]);
  const { data: source } = useApi(() => (claim ? api.sources.get(claim.source_id) : Promise.resolve(null)), [claim?.source_id]);
  const { data: mentions } = useApi(() => (id ? api.claims.mentions(id) : Promise.resolve([])), [id]);
  const { data: selectors } = useApi(() => (id ? api.selectors.forClaim(id) : Promise.resolve([])), [id]);
  const { data: grade } = useApi(() => (id ? api.selectors.claimGrade(id).catch(() => null) : Promise.resolve(null)), [id, claim?.knowledge_state]);
  const { data: archive } = useApi(() => (id ? api.archive.forClaim(id).catch(() => null) : Promise.resolve(null)), [id]);

  if (!id) return <EmptyState title="Claim belirtilmedi" />;
  if (loading) return <div className="mx-auto max-w-4xl"><SkeletonDetail /></div>;
  if (error) return <div className="mx-auto max-w-4xl"><ErrorState error={error} onRetry={reload} /></div>;
  if (!claim) return null;

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <header className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <ConfidenceBadge state={claim.knowledge_state} confidence={claim.confidence} />
          {grade && (
            <span
              className="rounded border border-border px-1.5 py-0.5 font-mono text-xs text-text-secondary"
              title={`NATO/Admiralty: ${grade.source_label} kaynak · ${grade.info_label.toLowerCase()} bilgi`}
            >
              {grade.code}
            </span>
          )}
          {claim.superseded_by_claim_id && (
            <Link href={`/claims/view?id=${claim.superseded_by_claim_id}`} className="text-xs text-priority-medium-text hover:underline">
              Daha yeni bir claim bunun yerini aldı →
            </Link>
          )}
        </div>
        {/* Claim metni toplanan kaynaktan gelir — güvenilmeyen veri (Q22). */}
        <blockquote className="rounded-lg border border-dashed border-white/15 bg-black/20 p-4 text-base leading-relaxed text-pretty text-foreground">
          {claim.text}
        </blockquote>
        <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-text-secondary">
          {source && (
            <Link href={`/sources/${source.id}`} className="inline-flex items-center gap-1.5 hover:text-foreground">
              <Database aria-hidden className="h-3.5 w-3.5" /> {source.name}
            </Link>
          )}
          {claim.about_entity_id && (
            <Link href={`/entities/${claim.about_entity_id}`} className="inline-flex items-center gap-1.5 hover:text-foreground">
              <Network aria-hidden className="h-3.5 w-3.5" /> özne: entity
            </Link>
          )}
          {claim.about_event_id && (
            <Link href={`/events/${claim.about_event_id}`} className="inline-flex items-center gap-1.5 hover:text-foreground">
              <CalendarClock aria-hidden className="h-3.5 w-3.5" /> özne: olay
            </Link>
          )}
          <span className="font-mono text-xs text-text-tertiary">
            geçerli {new Date(claim.valid_from).toLocaleDateString("tr-TR")}
            {claim.valid_to ? ` → ${new Date(claim.valid_to).toLocaleDateString("tr-TR")}` : " → bugün"}
          </span>
        </div>
      </header>

      <section className="flex flex-col gap-2">
        <ConfidenceExplainDisclosure claimId={claim.id} />
        <WhyMattersDisclosure claimId={claim.id} />
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="text-sm font-medium uppercase tracking-wide text-text-tertiary">Bu iddiayı başka kim söylüyor?</h2>
        <p className="text-xs text-pretty text-text-secondary">
          Haber araması iddianın başlığıyla yapılır. Bağımsız bir yayıncının haberini gözleme çevir: Promote Kuyruğu ve
          Doğrulama ekranı onu bu claim&apos;in olası doğrulayıcısı olarak önerir.
        </p>
        <EnrichmentPanel targetId={`claim:${claim.id}`} />
      </section>

      {mentions && mentions.length > 0 && (
        <section className="flex flex-col gap-2">
          <h2 className="text-sm font-medium uppercase tracking-wide text-text-tertiary">Adı geçenler</h2>
          <div className="flex flex-wrap gap-1.5">
            {mentions.map((m) => (
              <Link key={m.entity_id} href={`/entities/${m.entity_id}`} className="rounded-md border border-border bg-surface px-2 py-1 text-sm hover:border-white/25">
                {m.name} <span className="text-xs text-text-tertiary">{m.entity_type}</span>
              </Link>
            ))}
          </div>
        </section>
      )}

      <section className="flex flex-col gap-2">
        <h2 className="text-sm font-medium uppercase tracking-wide text-text-tertiary">Seçiciler</h2>
        {selectors && selectors.length > 0 ? (
          <div className="flex flex-wrap gap-1.5">
            {selectors.map((s) => (
              <SelectorChip key={s.id} id={s.id} kind={s.kind} value={s.value} />
            ))}
          </div>
        ) : (
          <p className="text-sm text-text-tertiary">Bu claim&apos;in kaynak metninde makine-okunur gösterge yok.</p>
        )}
      </section>

      {archive && (
        <section className="flex flex-col gap-2">
          <h2 className="text-sm font-medium uppercase tracking-wide text-text-tertiary">Kaynak arşivi</h2>
          <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-surface px-3 py-2 text-sm">
            <Archive aria-hidden className="h-4 w-4 text-text-tertiary" />
            <span className="text-foreground">{archive.archive_status_label}</span>
            {archive.content_hash && <span className="font-mono text-xs text-text-tertiary">sha256 {archive.content_hash.slice(0, 16)}…</span>}
            {archive.archive_url && (
              <a href={archive.archive_url} target="_blank" rel="noopener noreferrer nofollow" className="truncate font-mono text-xs text-text-secondary hover:text-foreground">
                {archive.archive_url}
              </a>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
