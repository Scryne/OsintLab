"use client";

import { Check, Minus } from "lucide-react";
import { cn } from "@/lib/utils";

/** Faz 16 — toplu seçim için. Native `<input type="checkbox">` üzerine kuruldu (kendi
 * durumunu yöneten bir widget değil): klavye, form ve ekran okuyucu davranışı tarayıcıdan
 * geliyor, görsel katman sadece üstüne biniyor. `indeterminate` görünümü "başlıktaki seç"
 * kutusunun üçüncü hâli için — bazı seçili, hepsi değil. */
export function Checkbox({
  checked,
  indeterminate = false,
  onCheckedChange,
  className,
  "aria-label": ariaLabel,
}: {
  checked: boolean;
  indeterminate?: boolean;
  onCheckedChange: (checked: boolean) => void;
  className?: string;
  "aria-label": string;
}) {
  const active = checked || indeterminate;
  return (
    <span className={cn("relative inline-flex h-4 w-4 shrink-0", className)}>
      <input
        type="checkbox"
        checked={checked}
        aria-label={ariaLabel}
        aria-checked={indeterminate ? "mixed" : checked}
        onChange={(e) => onCheckedChange(e.target.checked)}
        className="peer absolute inset-0 h-full w-full cursor-pointer appearance-none rounded-[5px] border border-white/25 bg-white/5 transition-colors checked:border-brand-accent checked:bg-brand-accent hover:border-white/45 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background"
        style={active && !checked ? { borderColor: "var(--brand-accent)", background: "var(--brand-accent)" } : undefined}
      />
      {active && (
        <span className="pointer-events-none absolute inset-0 flex items-center justify-center text-[var(--brand-accent-foreground)]">
          {checked ? <Check aria-hidden className="h-3 w-3" strokeWidth={3} /> : <Minus aria-hidden className="h-3 w-3" strokeWidth={3} />}
        </span>
      )}
    </span>
  );
}
