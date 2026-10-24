"use client";

import { useState } from "react";
import { FileDown, FileText } from "lucide-react";
import { API_BASE } from "@/lib/api";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const TLP = {
  CLEAR: "TLP:CLEAR — sınırsız",
  GREEN: "TLP:GREEN — topluluk içi",
  AMBER: "TLP:AMBER — kurum içi",
  "AMBER+STRICT": "TLP:AMBER+STRICT — yalnız kendi kurumu",
  RED: "TLP:RED — yalnız adı geçenler",
} as const;

/** Faz 35 — investigation raporu. Rapor deterministik: LLM yazmaz, yorum yalnızca kullanıcının
 * kendi Analiz/Sonuç metnidir. TLP dağıtım etiketi kullanıcının kararı. HTML, betik çalıştırmayan
 * bir CSP ile döner ve yazdırılabilir (tarayıcıdan PDF'e). */
export function ReportExport({ investigationId }: { investigationId: string }) {
  const [tlp, setTlp] = useState<keyof typeof TLP>("CLEAR");
  const base = `${API_BASE}/investigations/${investigationId}/report?tlp=${encodeURIComponent(tlp)}`;
  return (
    <div className="mt-3 flex flex-wrap items-center gap-2">
      <Select value={tlp} items={TLP} onValueChange={(v) => v && setTlp(v as keyof typeof TLP)}>
        <SelectTrigger className="h-8 w-60" aria-label="Rapor dağıtım etiketi (TLP)">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {Object.entries(TLP).map(([k, label]) => (
            <SelectItem key={k} value={k}>
              {label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <a
        href={`${base}&format=html`}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex h-8 items-center gap-1.5 rounded-md border border-border px-2.5 text-sm text-foreground hover:border-white/25"
      >
        <FileText aria-hidden className="h-3.5 w-3.5" />
        Raporu aç (yazdırılabilir)
      </a>
      <a href={`${base}&format=md&download=true`} className="inline-flex h-8 items-center gap-1.5 rounded-md border border-border px-2.5 text-sm text-foreground hover:border-white/25">
        <FileDown aria-hidden className="h-3.5 w-3.5" />
        Markdown indir
      </a>
    </div>
  );
}
