"use client";

import { useState } from "react";
import Link from "next/link";
import { Check, Eye, Flag, Star, X } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import type { InboxItem, InboxStatus } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/state";
import { PriorityBadge, PRIORITY_ORDER, PRIORITY_LABEL_TR } from "@/components/provenance/priority";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";

const TARGET_HREF: Record<string, (id: string) => string> = {
  Entity: (id) => `/entities/${id}`,
  Event: (id) => `/events/${id}`,
  Investigation: (id) => `/investigations/${id}`,
};

// Q14 — Ignore/Confirm/Reject/Investigate/Follow. Loglanır, v1'de algoritmayı otomatik
// etkilemez (bkz. app/monitoring.py).
const ACTIONS: { status: InboxStatus; label: string; icon: typeof Check }[] = [
  { status: "CONFIRMED", label: "Onayla", icon: Check },
  { status: "REJECTED", label: "Reddet", icon: X },
  { status: "INVESTIGATING", label: "Araştır", icon: Eye },
  { status: "FOLLOWED", label: "Takip et", icon: Star },
  { status: "IGNORED", label: "Yoksay", icon: Flag },
];

export default function InboxPage() {
  const [minPriority, setMinPriority] = useState<string>("INFO");
  const { data: items, error, loading, reload } = useApi(
    () => api.inbox.list({ min_priority: minPriority }),
    [minPriority]
  );

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="font-display text-2xl font-semibold text-foreground">Intelligence Inbox</h1>
          <p className="text-sm text-text-secondary">More signal, less noise.</p>
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

      {loading && <LoadingState />}
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
          <div className="mt-1 flex items-center gap-2 text-[11px] text-text-tertiary">
            <span className="font-mono">{new Date(item.created_at).toLocaleString("tr-TR")}</span>
            {href && (
              <Link href={href} className="text-brand-accent hover:underline">
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
