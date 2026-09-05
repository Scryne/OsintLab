"use client";

import { useState } from "react";
import Link from "next/link";
import { Database, Eye, FileCheck, Plus } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { InvestigationScope } from "@/components/forms/investigation-scope";
import { HypothesisEvidenceDialog } from "@/components/forms/hypothesis-evidence-dialog";
import { AddFindingDialog } from "@/components/forms/add-finding-dialog";
import { InvestigationNarrative } from "@/components/forms/investigation-narrative";
import { WorkflowRail } from "@/components/forms/workflow-rail";
import type { InvestigationStatus, KnowledgeState } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorState, EmptyState } from "@/components/ui/state";
import { SkeletonDetail } from "@/components/ui/skeleton";
import { ConfidenceBadge, ConfidenceRail } from "@/components/provenance/confidence";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogDescription,
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
  // Faz 13: tek çağrı — zincirin ara adımları (kaynaklar/gözlemler/claim'ler/kanıtlar)
  // graf'tan türetiliyor, ayrıca beyan edilmiyor.
  const { data: ws, error, loading, reload } = useApi(
    () => api.investigations.workspace(investigationId),
    [investigationId]
  );
  // `validated` bayrağı yalnızca findings ucunda var (Q17: kapanışta promote edilenler).
  const { data: findings, reload: reloadFindings } = useApi(
    () => api.investigations.findings(investigationId),
    [investigationId]
  );
  const [transitioning, setTransitioning] = useState(false);
  const [confidenceFilter, setConfidenceFilter] = useState<KnowledgeState | null>(null);

  function reloadAll() {
    reload();
    reloadFindings();
  }

  async function transition(to: InvestigationStatus) {
    setTransitioning(true);
    try {
      await api.investigations.transition(investigationId, to);
      toast(`Durum değişti: ${to}`, "success");
      reloadAll();
    } catch (err) {
      // Sonuç yazılmadan CLOSED denemesi 409 döner — mesaj ne yapılacağını söylüyor.
      toast(err instanceof Error ? err.message : "Geçiş başarısız", "error");
    } finally {
      setTransitioning(false);
    }
  }

  if (loading) return <SkeletonDetail />;
  if (error) return <ErrorState message={error.message} />;
  if (!ws) return null;

  const inv = ws.investigation;
  const visibleClaims = confidenceFilter
    ? ws.claims.filter((c) => c.knowledge_state === confidenceFilter)
    : ws.claims;

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <header>
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="font-display text-[2rem] font-semibold tracking-tight text-balance text-foreground">{inv.title}</h1>
          <Badge variant="outline">{inv.status}</Badge>
        </div>
        <p className="mt-1 text-sm text-text-secondary">{inv.research_question}</p>
        {inv.concluded_at && (
          <p className="mt-1 font-mono text-xs text-text-tertiary">
            {new Date(inv.concluded_at).toLocaleString("tr-TR")} tarihinde sonuca varıldı
          </p>
        )}
        <div className="mt-3 flex flex-wrap gap-1.5">
          {TRANSITIONS[inv.status].map((to) => (
            <Button key={to} size="sm" variant="outline" disabled={transitioning} onClick={() => transition(to)}>
              → {to}
            </Button>
          ))}
        </div>
        {inv.status === "RESOLVED" && !inv.conclusion && (
          <p className="mt-2 text-xs text-priority-medium-text">
            Kapatmak için önce Sonuç yazılmalı — kapanış, doğrulanmış bulguları Knowledge
            Graph&apos;a yükselten adım.
          </p>
        )}
      </header>

      <WorkflowRail steps={ws.steps} />

      {/* Zincir sırası (madde 30): Scope → Kaynaklar → Gözlemler → Claim'ler → Kanıtlar →
          Hipotezler → Analiz → Findings → Sonuç. */}
      <InvestigationScope investigationId={investigationId} />

      <DerivedSection
        title="Kaynaklar"
        icon={Database}
        count={ws.sources.length}
        empty="Kapsamdaki claim'lere henüz hiçbir kaynak atıf yapmadı."
      >
        {ws.sources.map((s) => (
          <Link
            key={s.id}
            href={`/sources/${s.id}`}
            className="flex items-center justify-between gap-2 rounded-md border border-border bg-surface px-3 py-2 text-sm transition-colors hover:border-white/20"
          >
            <span className="truncate text-foreground">{s.name}</span>
            <span className="shrink-0 font-mono text-xs text-text-tertiary tabular-nums">
              %{Math.round(s.reliability * 100)}
            </span>
          </Link>
        ))}
      </DerivedSection>

      <DerivedSection
        title="Gözlemler"
        icon={Eye}
        count={ws.observations.length}
        empty="Bu araştırmadaki claim'lerin hiçbiri bir gözlemden promote edilmemiş (elle girilmiş)."
      >
        {ws.observations.map((o) => (
          <div key={o.id} className="rounded-md border border-border bg-surface px-3 py-2">
            <p className="truncate text-sm text-foreground">{o.headline}</p>
            {o.source_url && (
              <a
                href={o.source_url}
                target="_blank"
                rel="noreferrer"
                className="mt-0.5 block truncate font-mono text-[11px] text-text-tertiary underline decoration-white/20 underline-offset-2 hover:text-foreground"
              >
                {o.source_url}
              </a>
            )}
          </div>
        ))}
      </DerivedSection>

      <section>
        <SectionHeader title="Claim'ler" count={ws.claims.length} />
        {ws.claims.length === 0 ? (
          <EmptyState
            title="Henüz claim yok"
            description="Kapsama bir entity ekle ya da bir gözlemi promote et."
          />
        ) : (
          // Design.md imza öğesinin ikinci yarısı: spektrum sadece Entity'de bir filtre
          // olarak duruyordu, oysa "hangi bilgi ne kadar sağlam" sorusu bir investigation
          // içinde en az onun kadar anlamlı — kapanışta hangi claim'in finding olacağına
          // karar verirken sorulan soru tam olarak bu.
          <div className="flex flex-col gap-4 sm:flex-row sm:gap-6">
            <div className="shrink-0 border-b border-border pb-3 sm:w-40 sm:border-b-0 sm:border-r sm:pr-4 sm:pb-0">
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-text-tertiary">
                Confidence Spectrum
              </p>
              <ConfidenceRail active={confidenceFilter} onSelect={setConfidenceFilter} />
            </div>
            <div className="flex min-w-0 flex-1 flex-col gap-2">
              {visibleClaims.length === 0 ? (
                <EmptyState
                  title="Bu güven seviyesinde claim yok"
                  description="Spektrum'dan seçimi kaldırıp hepsini görebilirsin."
                />
              ) : null}
              {visibleClaims.map((c) => (
              <div
                key={c.id}
                className={`rounded-lg border border-border bg-surface p-3 ${c.superseded ? "opacity-60" : ""}`}
              >
                <div className="flex flex-wrap items-center gap-1.5">
                  <ConfidenceBadge state={c.knowledge_state} confidence={c.confidence} />
                  {/* Kapsamdan gelen bir claim ile bulgu ilan edilmiş bir claim aynı şey
                      değil; karıştırmak "neyi bulgu saydım" sorusunu bulanıklaştırır. */}
                  {c.is_finding && <Badge variant="secondary">finding</Badge>}
                  {c.superseded && <Badge variant="outline">yerini aldı</Badge>}
                </div>
                <p className={`mt-1 text-sm text-foreground ${c.superseded ? "line-through decoration-white/30" : ""}`}>
                  {c.headline}
                </p>
              </div>
              ))}
            </div>
          </div>
        )}
      </section>

      <DerivedSection
        title="Kanıtlar"
        icon={FileCheck}
        count={ws.evidence.length}
        empty="Bu araştırmanın claim'lerine bağlı bir kanıt yok."
      >
        {ws.evidence.map((e) => (
          <div key={`${e.id}-${e.stance}`} className="flex flex-wrap items-center gap-2 rounded-md border border-border bg-surface px-3 py-2 text-sm">
            <Badge variant={e.stance === "CONTRADICTS" ? "destructive" : "outline"}>
              {e.stance === "CONTRADICTS" ? "çürütüyor" : "destekliyor"}
            </Badge>
            <span className="text-foreground">{e.evidence_type}</span>
            {e.content_hash && (
              <span className="font-mono text-[11px] text-text-tertiary">{e.content_hash.slice(0, 12)}…</span>
            )}
          </div>
        ))}
      </DerivedSection>

      <section>
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-medium uppercase tracking-wide text-text-tertiary">
            Hipotezler {ws.hypotheses.length > 0 && `(${ws.hypotheses.length})`}
          </h2>
          <NewHypothesisDialog investigationId={investigationId} onCreated={reloadAll} />
        </div>
        {ws.hypotheses.length === 0 ? (
          <EmptyState
            title="Henüz hipotez yok"
            description="Sınanabilir bir hipotez yaz; kanıtları ona bağlayarak destekleyip çürütebilirsin."
            action={<NewHypothesisDialog investigationId={investigationId} onCreated={reloadAll} />}
          />
        ) : (
          <div className="flex flex-col gap-2">
            {ws.hypotheses.map((h) => (
              <div key={h.id} className="flex items-start justify-between gap-3 rounded-lg border border-border bg-surface p-3">
                <p className="text-sm text-foreground">{h.text}</p>
                <div className="flex shrink-0 items-center gap-1.5">
                  <HypothesisEvidenceDialog hypothesisId={h.id} onLinked={reloadAll} />
                  <Badge variant="outline">{h.status}</Badge>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <InvestigationNarrative
        investigationId={investigationId}
        field="analysis"
        value={inv.analysis}
        label="Analiz"
        placeholder="Kanıtlar ne söylüyor, hangi hipotez ayakta kaldı, hangi boşluk kapanmadı?"
        hint="Henüz analiz yazılmadı. Muhakemeni buraya yazmazsan, sonuca nasıl vardığın altı ay sonra kayıp olur."
        onSaved={reloadAll}
      />

      <section>
        <div className="mb-2 flex items-center justify-between gap-3">
          <h2 className="text-sm font-medium uppercase tracking-wide text-text-tertiary">
            Findings {findings && findings.length > 0 && `(${findings.length})`}
          </h2>
          <AddFindingDialog investigationId={investigationId} onAdded={reloadAll} />
        </div>
        {!findings || findings.length === 0 ? (
          <EmptyState
            title="Henüz finding eklenmedi"
            description="Findings, kapanışta Knowledge Graph'a yükselecek claim'ler — sadece doğrulanmış olanlar."
          />
        ) : (
          <div className="flex flex-col gap-2">
            {findings.map((f) => (
              <div key={f.id} className="flex items-start justify-between gap-3 rounded-lg border border-border bg-surface p-3">
                <p className="text-sm text-foreground">{f.headline}</p>
                <div className="flex shrink-0 items-center gap-2">
                  {f.validated && <Badge variant="secondary">validated</Badge>}
                  <ConfidenceBadge state={f.knowledge_state} confidence={f.confidence} />
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <InvestigationNarrative
        investigationId={investigationId}
        field="conclusion"
        value={inv.conclusion}
        label="Sonuç"
        placeholder="Araştırma sorusunun cevabı — ve ne kadar güvenle."
        hint="Henüz sonuç yazılmadı. Kapatmak (CLOSED) için gerekli."
        onSaved={reloadAll}
      />
    </div>
  );
}

function SectionHeader({ title, count }: { title: string; count: number }) {
  return (
    <h2 className="mb-2 text-sm font-medium uppercase tracking-wide text-text-tertiary">
      {title} {count > 0 && `(${count})`}
    </h2>
  );
}

/** Türetilen adımlar — burada "ekle" butonu YOK, bilerek: bu bölümler graf'tan okunuyor.
 * Kaynak eklemek için bir claim'e kaynak atfedilir, gözlem eklemek için gözlem promote
 * edilir. Buraya bir "ekle" koymak, aynı bağı ikinci kez elle kurmak demek olurdu. */
function DerivedSection({
  title,
  icon: Icon,
  count,
  empty,
  children,
}: {
  title: string;
  icon: typeof Database;
  count: number;
  empty: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <h2 className="mb-2 flex items-center gap-1.5 text-sm font-medium uppercase tracking-wide text-text-tertiary">
        <Icon aria-hidden className="h-3.5 w-3.5" />
        {title} {count > 0 && `(${count})`}
      </h2>
      {count === 0 ? (
        <p className="rounded-lg border border-border bg-surface px-3 py-2.5 text-xs text-text-tertiary">{empty}</p>
      ) : (
        <div className="flex flex-col gap-1.5">{children}</div>
      )}
    </section>
  );
}

function NewHypothesisDialog({ investigationId, onCreated }: { investigationId: string; onCreated: () => void }) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    if (!text.trim()) return;
    setSubmitting(true);
    try {
      await api.investigations.createHypothesis(investigationId, text.trim());
      toast("Hipotez eklendi", "success");
      setText("");
      setOpen(false);
      onCreated();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Eklenemedi", "error");
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
            Hipotez
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Yeni hipotez</DialogTitle>
          <DialogDescription>Bu araştırmaya sınanabilir bir hipotez ekler. Kanıt daha sonra hipoteze bağlanır.</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="hypothesis-text">Hipotez</Label>
          <Textarea
            id="hypothesis-text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="H1: Company X, Organization Y tarafından doğrudan kontrol ediliyor."
            rows={3}
          />
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
