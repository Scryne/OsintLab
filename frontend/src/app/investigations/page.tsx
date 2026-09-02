"use client";

import Link from "next/link";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { Badge } from "@/components/ui/badge";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/state";

export default function InvestigationsPage() {
  const { data: investigations, error, loading, reload } = useApi(() => api.investigations.list(), []);

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <div>
        <h1 className="font-display text-2xl font-semibold text-foreground">Investigation&apos;lar</h1>
        <p className="text-sm text-text-secondary">Research Question → Findings → Conclusion.</p>
      </div>

      {loading && <LoadingState />}
      {error && <ErrorState message={error.message} onRetry={reload} />}
      {!loading && !error && investigations?.length === 0 && <EmptyState title="Henüz investigation yok" />}

      <div className="flex flex-col gap-2">
        {investigations?.map((inv) => (
          <Link
            key={inv.id}
            href={`/investigations/${inv.id}`}
            className="flex items-center justify-between rounded-lg border border-border bg-surface p-4 transition-colors hover:bg-surface-raised"
          >
            <div>
              <p className="text-sm font-medium text-foreground">{inv.title}</p>
              <p className="text-xs text-text-tertiary">{inv.research_question}</p>
            </div>
            <Badge variant="outline">{inv.status}</Badge>
          </Link>
        ))}
      </div>
    </div>
  );
}
