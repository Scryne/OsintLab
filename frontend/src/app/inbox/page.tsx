"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Check, Eye, Flag, Star, X } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import type { InboxItem, InboxStatus } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ErrorState, EmptyState } from "@/components/ui/state";
import { SkeletonRows } from "@/components/ui/skeleton";
import { PriorityBadge, PRIORITY_ORDER, PRIORITY_LABEL_TR } from "@/components/provenance/priority";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";

const TARGET_HREF: Record<string, (id: string) => string> = {
  Entity: (id) => `/entities/${id}`,
  Event: (id) => `/events/${id}`,
  Investigation: (id) => `/investigations/${id}`,
  // Faz 12'de liste sayfasına bağlanıyordu (detay sayfası yoktu); Faz 13'te düzeltildi.
  Source: (id) => `/sources/${id}`,
};

/** Faz 12 — NEW_OBSERVATION öğesinin detayı: hangi başlıklar geldi, bildiğimiz hangi
 * entity'lerden bahsediyor. Bunlar olmadan bildirim "3 yeni içerik" deyip kullanıcıyı
 * Gözlemler sayfasında arama yapmaya zorlardı; öncelik gerekçesi de görünmezdi. */
function ScanDetail({ detail }: { detail: Record<string, unknown> }) {
  const headlines = Array.isArray(detail.headlines) ? (detail.headlines as string[]) : [];
  const matched = Array.isArray(detail.matched_entities)
    ? (detail.matched_entities as { id: string; name: string }[])
    : [];
  const total = Array.isArray(detail.observation_ids) ? detail.observation_ids.length : 0;
  if (headlines.length === 0) return null;

  return (
    <div className="mt-2 flex flex-col gap-1.5">
      <ul className="flex flex-col gap-0.5 text-xs text-text-secondary">
        {headlines.map((h, i) => (
          <li key={i} className="truncate">
            · {h}
          </li>
        ))}
        {total > headlines.length && (
          <li className="text-text-tertiary">· ve {total - headlines.length} tane daha</li>
        )}
      </ul>
      {/* F58: bildirim "17 yeni içerik" diyordu ama o gözleme gitmenin yolu yoktu —
          observation_ids zaten detayda duruyordu, eksik olan yalnızca bu bağdı. */}
      {total > 0 && (
        <Link
          href={`/observations?ids=${(detail.observation_ids as string[]).join(",")}`}
          className="w-fit text-xs text-text-secondary underline decoration-white/20 underline-offset-2 hover:text-foreground hover:decoration-white/50"
        >
          {total} gözlemin tümünü aç →
        </Link>
      )}
      {matched.length > 0 && (
        <p className="text-[11px] text-text-tertiary">
          Bildiğimiz entity&apos;ler:{" "}
          {matched.map((m, i) => (
            <span key={m.id}>
              {i > 0 && ", "}
              <Link
                href={`/entities/${m.id}`}
                className="text-text-secondary underline decoration-white/20 underline-offset-2 hover:text-foreground"
              >
                {m.name}
              </Link>
            </span>
          ))}
        </p>
      )}
    </div>
  );
}

// Q14 — Ignore/Confirm/Reject/Investigate/Follow. Loglanır, v1'de algoritmayı otomatik
// etkilemez (bkz. app/monitoring.py).
const ACTIONS: { status: InboxStatus; label: string; icon: typeof Check }[] = [
  { status: "CONFIRMED", label: "Onayla", icon: Check },
  { status: "REJECTED", label: "Reddet", icon: X },
  { status: "INVESTIGATING", label: "Araştır", icon: Eye },
  { status: "FOLLOWED", label: "Takip et", icon: Star },
  { status: "IGNORED", label: "Yoksay", icon: Flag },
];

/** Zamanlanmış tarama (Faz 12) en sık 3 saatte bir çalışıyor; 30 sn'lik yoklama "arkada bir
 * şey düştüyse görürüm" için fazlasıyla yeterli, üstelik sekme görünmezken duruyor. */
const INBOX_POLL_MS = 30_000;

export default function InboxPage() {
  const [minPriority, setMinPriority] = useState<string>("INFO");
  const { data: items, error, loading, reload, updatedAt } = useApi(
    () => api.inbox.list({ min_priority: minPriority }),
    [minPriority],
    { pollMs: INBOX_POLL_MS }
  );

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="font-display text-[2rem] font-semibold tracking-tight text-foreground">Intelligence Inbox</h1>
          <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-text-secondary">
            More signal, less noise.
            {/* Sayfanın canlı olduğunu SÖYLEMEK gerekiyor: sessizce tazelenen bir liste ile
                donmuş bir liste ekranda birbirinin aynı görünür — kullanıcı yine elle
                yenilemeye devam ederdi. */}
            <LiveIndicator updatedAt={updatedAt} />
          </p>
        </div>
        <Select value={minPriority} onValueChange={(value) => value && setMinPriority(value)}>
          <SelectTrigger className="w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {PRIORITY_ORDER.map((p) => (
              <SelectItem key={p} value={p}>
                {PRIORITY_LABEL_TR[p]}+
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {loading && <SkeletonRows count={4} />}
      {error && <ErrorState message={error.message} onRetry={reload} />}
      {!loading && !error && items?.length === 0 && (
        <EmptyState title="Inbox boş" description="Bu eşiğin üzerinde bekleyen bir şey yok." />
      )}

      <div className="flex flex-col gap-2">
        {items?.map((item) => (
          <InboxRow key={item.id} item={item} onChanged={reload} />
        ))}
      </div>
    </div>
  );
}

function LiveIndicator({ updatedAt }: { updatedAt: Date | null }) {
  // Saniye sayacı kendi başına ilerlemeli; veri değişmese de "kaç sn önce" tazelenmeli.
  const [, force] = useState(0);
  useEffect(() => {
    const t = window.setInterval(() => force((n) => n + 1), 10_000);
    return () => window.clearInterval(t);
  }, []);

  if (!updatedAt) return null;
  const secs = Math.max(0, Math.round((Date.now() - updatedAt.getTime()) / 1000));
  const label = secs < 60 ? `${secs} sn önce` : `${Math.round(secs / 60)} dk önce`;
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-text-tertiary">
      <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-priority-low/80" />
      canlı · {label} güncellendi
    </span>
  );
}

function InboxRow({ item, onChanged }: { item: InboxItem; onChanged: () => void }) {
  const [busy, setBusy] = useState(false);
  const href = TARGET_HREF[item.target_type]?.(item.target_id);
  const acted = item.status !== "NEW";

  async function act(status: InboxStatus) {
    setBusy(true);
    try {
      await api.inbox.updateStatus(item.id, status);
      onChanged();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <PriorityBadge priority={item.priority} />
            <span className="text-[11px] uppercase tracking-wide text-text-tertiary">{item.item_type}</span>
          </div>
          <p className="mt-1 text-sm text-foreground">{item.title}</p>
          {item.item_type === "NEW_OBSERVATION" && <ScanDetail detail={item.detail} />}
          <div className="mt-1 flex items-center gap-2 text-[11px] text-text-tertiary">
            <span className="font-mono">{new Date(item.created_at).toLocaleString("tr-TR")}</span>
            {href && (
              <Link href={href} className="text-text-secondary underline decoration-white/20 underline-offset-2 hover:text-foreground hover:decoration-white/50">
                hedefe git →
              </Link>
            )}
          </div>
        </div>
        {acted && <Badge variant="outline">{item.status}</Badge>}
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {ACTIONS.map(({ status, label, icon: Icon }) => (
          <Button
            key={status}
            size="sm"
            variant={item.status === status ? "secondary" : "outline"}
            disabled={busy}
            onClick={() => act(status)}
            className={cn("h-7 px-2 text-xs")}
          >
            <Icon className="h-3.5 w-3.5" />
            {label}
          </Button>
        ))}
      </div>
    </div>
  );
}
