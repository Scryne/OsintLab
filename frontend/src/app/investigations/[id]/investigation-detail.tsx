"use client";

import { useState } from "react";
import { Plus } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import type { InvestigationStatus } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/state";
import { ConfidenceBadge } from "@/components/provenance/confidence";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";

const TRANSITIONS: Record<InvestigationStatus, InvestigationStatus[]> = {
  OPEN: ["ACTIVE", "ARCHIVED"],
  ACTIVE: ["PAUSED", "RESOLVED", "ARCHIVED"],
  PAUSED: ["ACTIVE", "ARCHIVED"],
  RESOLVED: ["ACTIVE", "CLOSED", "ARCHIVED"],
  CLOSED: ["ARCHIVED"],
  ARCHIVED: [],
};

export function InvestigationDetail({ investigationId }: { investigationId: string }) {
  const toast = useToast();
  const { data: investigation, error, loading, reload } = useApi(
    () => api.investigations.get(investigationId),
    [investigationId]
  );
  const { data: findings, reload: reloadFindings } = useApi(
    () => api.investigations.findings(investigationId),
    [investigationId]
  );
  const { data: hypotheses, reload: reloadHypotheses } = useApi(
    () => api.investigations.hypotheses(investigationId),
    [investigationId]
  );
  const [transitioning, setTransitioning] = useState(false);

  async function transition(to: InvestigationStatus) {
    setTransitioning(true);
    try {
      await api.investigations.transition(investigationId, to);
      toast(`Durum değişti: ${to}`, "success");
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
          <h1 className="font-display text-[2rem] font-semibold tracking-tight text-foreground">{investigation.title}</h1>
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
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-medium uppercase tracking-wide text-text-tertiary">Hipotezler</h2>
          <NewHypothesisDialog investigationId={investigationId} onCreated={reloadHypotheses} />
        </div>
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

function NewHypothesisDialog({ investigationId, onCreated }: { investigationId: string; onCreated: () => void }) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (!text.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.investigations.createHypothesis(investigationId, text.trim());
      toast("Hipotez eklendi", "success");
      setText("");
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
          <Button size="sm" variant="outline">
            <Plus aria-hidden className="h-4 w-4" />
            Yeni Hipotez
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Yeni hipotez ekle</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="hypothesis-text">Metin</Label>
            <Textarea
              id="hypothesis-text"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="ör. H1: Şirket X, Kurum Y tarafından doğrudan kontrol ediliyor."
              rows={3}
            />
          </div>
          {error && <p className="text-sm text-priority-critical">{error}</p>}
        </div>
        <DialogFooter>
          <Button onClick={submit} disabled={submitting || !text.trim()}>
            {submitting ? "Ekleniyor…" : "Ekle"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
