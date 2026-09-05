import { cn } from "@/lib/utils";
import type { Priority } from "@/lib/types";

// Priority/Alarm Scale — sadece Intelligence Inbox'a özel, Confidence Spectrum'dan bilerek
// ayrı bir renk ailesinde (mor-kırmızı). bkz. DESIGN.md "Colors".
export const PRIORITY_ORDER: Priority[] = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"];

export const PRIORITY_COLOR_VAR: Record<Priority, string> = {
  CRITICAL: "var(--priority-critical)",
  HIGH: "var(--priority-high)",
  MEDIUM: "var(--priority-medium)",
  LOW: "var(--priority-low)",
  INFO: "var(--priority-info)",
};

/** Metin rengi zeminden AYRI bir token — bkz. globals.css'teki kontrast notu. Zemin/glow
 * ham rengi kullanmaya devam eder (dekoratif, 3:1 eşiği yeterli), metin okunur olanı. */
export const PRIORITY_TEXT_VAR: Record<Priority, string> = {
  CRITICAL: "var(--priority-critical-text)",
  HIGH: "var(--priority-high-text)",
  MEDIUM: "var(--priority-medium-text)",
  LOW: "var(--priority-low-text)",
  INFO: "var(--priority-info-text)",
};

export const PRIORITY_LABEL_TR: Record<Priority, string> = {
  CRITICAL: "Kritik",
  HIGH: "Yüksek",
  MEDIUM: "Orta",
  LOW: "Düşük",
  INFO: "Bilgi",
};

export function PriorityBadge({ priority, className }: { priority: Priority; className?: string }) {
  const color = PRIORITY_COLOR_VAR[priority];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold uppercase tracking-wide",
        className
      )}
      style={{
        backgroundColor: `color-mix(in oklch, ${color} 22%, transparent)`,
        color: PRIORITY_TEXT_VAR[priority],
        boxShadow: `0 0 10px color-mix(in oklch, ${color} 35%, transparent)`,
      }}
    >
      {PRIORITY_LABEL_TR[priority]}
    </span>
  );
}
