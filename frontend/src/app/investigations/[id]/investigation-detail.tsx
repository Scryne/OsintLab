"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import type { InvestigationStatus } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/state";
import { ConfidenceBadge } from "@/components/provenance/confidence";

const TRANSITIONS: Record<InvestigationStatus, InvestigationStatus[]> = {
  OPEN: ["ACTIVE", "ARCHIVED"],
  ACTIVE: ["PAUSED", "RESOLVED", "ARCHIVED"],
  PAUSED: ["ACTIVE", "ARCHIVED"],
  RESOLVED: ["ACTIVE", "CLOSED", "ARCHIVED"],
  CLOSED: ["ARCHIVED"],
  ARCHIVED: [],
};

export function InvestigationDetail({ investigationId }: { investigationId: string }) {
  const { data: investigation, error, loading, reload } = useApi(
    () => api.investigations.get(investigationId),
    [investigationId]
  );
  const { data: findings, reload: reloadFindings } = useApi(
    () => api.investigations.findings(investigationId),
    [investigationId]
  );
  const { data: hypotheses } = useApi(() => api.investigations.hypotheses(investigationId), [investigationId]);
  const [transitioning, setTransitioning] = useState(false);

  async function transition(to: InvestigationStatus) {
    setTransitioning(true);
    try {
      await api.investigations.transition(investigationId, to);
      reload();
      reloadFindings();
    } finally {
      setTransitioning(false);
    }
  }

  if (loading) return <LoadingState label="Investigation yükleniyor…" />;
  if (error) return <ErrorState message={error.message} />;
  if (!investigation) return null;

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <header>
        <div className="flex items-center gap-2">
          <h1 className="font-display text-2xl font-semibold text-foreground">{investigation.title}</h1>
          <Badge variant="outline">{investigation.status}</Badge>
        </div>
        <p className="mt-1 text-sm text-text-secondary">{investigation.research_question}</p>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {TRANSITIONS[investigation.status].map((to) => (
            <Button key={to} size="sm" variant="outline" disabled={transitioning} onClick={() => transition(to)}>
              → {to}
            </Button>
          ))}
        </div>
      </header>

      <section>
        <h2 className="mb-2 text-sm font-medium uppercase tracking-wide text-text-tertiary">Findings</h2>
        {!findings || findings.length === 0 ? (
          <EmptyState title="Henüz finding eklenmedi" />
        ) : (
          <div className="flex flex-col gap-2">
            {findings.map((f) => (
              <div key={f.id} className="flex items-start justify-between gap-3 rounded-lg border border-border bg-surface p-3">
                <p className="text-sm text-foreground">{f.text}</p>
                <div className="flex shrink-0 items-center gap-2">
                  {f.validated && <Badge variant="secondary">validated</Badge>}
                  <ConfidenceBadge state={f.knowledge_state} confidence={f.confidence} />
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-2 text-sm font-medium uppercase tracking-wide text-text-tertiary">Hipotezler</h2>
        {!hypotheses || hypotheses.length === 0 ? (
          <EmptyState title="Henüz hipotez yok" />
        ) : (
          <div className="flex flex-col gap-2">
            {hypotheses.map((h) => (
              <div key={h.id} className="flex items-start justify-between gap-3 rounded-lg border border-border bg-surface p-3">
                <p className="text-sm text-foreground">{h.text}</p>
                <Badge variant="outline" className="shrink-0">
                  {h.status}
                </Badge>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
