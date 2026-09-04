"use client";

import { Check } from "lucide-react";
import type { WorkflowStep } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Proje-Fikri.md madde 30'un zinciri, olduğu gibi:
 * Research Question → Scope → Entities → Sources → Observations → Claims → Evidence →
 * Hypotheses → Analysis → Findings → Conclusion.
 *
 * "Entities" ayrı bir adım olarak gösterilmiyor çünkü Scope'un kendisi entity/event
 * seçmekten ibaret — ikisini ayrı kutu yapmak, aynı işi iki kez yapılacakmış gibi
 * gösterirdi.
 *
 * Şerit bir ilerleme ÇUBUĞU değil, bir kontrol listesi: adımlar sırayla dolmak zorunda
 * değil (gerçek araştırma böyle ilerlemiyor — hipotez bazen kanıttan önce yazılıyor).
 * Amaç "neresi boş kalmış" sorusunu tek bakışta cevaplamak. */
const STEPS: { key: WorkflowStep; label: string }[] = [
  { key: "research_question", label: "Soru" },
  { key: "scope", label: "Kapsam" },
  { key: "sources", label: "Kaynaklar" },
  { key: "observations", label: "Gözlemler" },
  { key: "claims", label: "Claim'ler" },
  { key: "evidence", label: "Kanıtlar" },
  { key: "hypotheses", label: "Hipotezler" },
  { key: "analysis", label: "Analiz" },
  { key: "findings", label: "Findings" },
  { key: "conclusion", label: "Sonuç" },
];

export function WorkflowRail({ steps }: { steps: Record<WorkflowStep, boolean> }) {
  const done = STEPS.filter((s) => steps[s.key]).length;

  return (
    <section className="rounded-lg border border-border bg-surface p-4">
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <h2 className="text-sm font-medium uppercase tracking-wide text-text-tertiary">
          Araştırma Akışı
        </h2>
        <span className="font-mono text-xs text-text-tertiary tabular-nums">
          {done}/{STEPS.length}
        </span>
      </div>
      <ol className="flex flex-wrap items-center gap-x-1 gap-y-2">
        {STEPS.map((step, i) => (
          <li key={step.key} className="flex items-center gap-1">
            <span
              className={cn(
                "inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs transition-colors",
                steps[step.key]
                  ? "border-white/20 bg-white/10 text-foreground"
                  : "border-border bg-transparent text-text-tertiary"
              )}
            >
              {steps[step.key] && <Check aria-hidden className="h-3 w-3" />}
              {step.label}
            </span>
            {i < STEPS.length - 1 && (
              <span aria-hidden className="text-text-tertiary/50">
                ›
              </span>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}
