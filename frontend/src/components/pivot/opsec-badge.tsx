import { HardDrive, Radar, Radio } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Opsec } from "@/lib/types-pivot";

const VIEW: Record<Opsec, { label: string; icon: typeof Radar; cls: string }> = {
  // Pasif normal iş akışı — nötr. Aktif hedefe dokunur: priority-high, çünkü bu bir "dikkat"
  // işaretidir, epistemik bir durum değil (confidence rampası kullanılmaz).
  PASSIVE: { label: "Pasif", icon: Radar, cls: "border-border text-text-secondary" },
  LOCAL: { label: "Yerel", icon: HardDrive, cls: "border-border text-text-secondary" },
  ACTIVE: { label: "Aktif", icon: Radio, cls: "border-priority-high/40 text-priority-high-text" },
};

export function OpsecBadge({ opsec, title, className }: { opsec: Opsec; title?: string; className?: string }) {
  const v = VIEW[opsec];
  const Icon = v.icon;
  return (
    <span
      title={title}
      className={cn("inline-flex items-center gap-1 rounded-full border px-1.5 py-0.5 text-[10px] font-medium", v.cls, className)}
    >
      <Icon aria-hidden className="h-3 w-3" />
      {v.label}
    </span>
  );
}
