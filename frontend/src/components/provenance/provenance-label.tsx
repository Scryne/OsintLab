import { GitBranch, Pencil, Quote, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ProvenanceLabel } from "@/lib/types";

/**
 * Q15 — SOURCE FACT / AI ANALYSIS / SYSTEM INFERENCE / USER INTERPRETATION.
 * Bilinçli olarak RENKLE değil kenarlık-stili + ikonla ayrışıyor (bkz. DESIGN.md
 * Uygulama Notları) — üçüncü bir renk sistemi Confidence Spectrum + Priority Scale'i
 * sulandırırdı. USER_INTERPRETATION tek istisna: marka accent moru kullanıyor, çünkü bu
 * kategori kullanıcının kendi sesi.
 */
const CONFIG: Record<
  ProvenanceLabel,
  { label: string; icon: typeof Quote; border: string; italic: boolean; tint?: string }
> = {
  SOURCE_FACT: { label: "SOURCE FACT", icon: Quote, border: "border-l-2 border-solid border-text-secondary", italic: false },
  SYSTEM_INFERENCE: {
    label: "SYSTEM INFERENCE",
    icon: GitBranch,
    border: "border-l-2 border-dashed border-text-secondary",
    italic: false,
  },
  AI_ANALYSIS: {
    label: "AI ANALYSIS",
    icon: Sparkles,
    border: "border-l-2 border-dotted border-text-secondary",
    italic: true,
  },
  USER_INTERPRETATION: {
    label: "USER INTERPRETATION",
    icon: Pencil,
    border: "border-l-2 border-solid border-brand-accent",
    italic: false,
    tint: "bg-brand-accent/[0.04]",
  },
};

export function ProvenanceLabelTag({ type }: { type: ProvenanceLabel }) {
  const { label, icon: Icon } = CONFIG[type];
  return (
    <span className="inline-flex items-center gap-1 text-[10px] font-medium uppercase tracking-wider text-text-tertiary">
      <Icon aria-hidden className="h-3 w-3" />
      {label}
    </span>
  );
}

export function ProvenanceBlock({
  type,
  children,
  className,
}: {
  type: ProvenanceLabel;
  children: React.ReactNode;
  className?: string;
}) {
  const cfg = CONFIG[type];
  return (
    <div className={cn("rounded-r-md py-1.5 pl-3", cfg.border, cfg.tint, className)}>
      <ProvenanceLabelTag type={type} />
      <div className={cn("mt-1 text-sm", cfg.italic && "italic")}>{children}</div>
    </div>
  );
}
