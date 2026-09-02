"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { api } from "@/lib/api";
import type { WhyMattersReason } from "@/lib/types";
import { ProvenanceBlock } from "@/components/provenance/provenance-label";

/**
 * Q12 — "Why This Matters" kural+graph tabanlı gerekçe, backend'de LLM çağırmadan üretiliyor
 * (bkz. backend/app/recall.py). Bu yüzden Q15 etiketlemesinde SYSTEM_INFERENCE: sistemin
 * kendi çıkarımı, ham kaynak metni değil.
 */
export function WhyMattersDisclosure({ claimId }: { claimId: string }) {
  const [open, setOpen] = useState(false);
  const [reasons, setReasons] = useState<WhyMattersReason[] | null>(null);
  const [loading, setLoading] = useState(false);

  async function toggle() {
    if (!open && reasons === null) {
      setLoading(true);
      try {
        const res = await api.claims.whyMatters(claimId);
        setReasons(res.reasons);
      } finally {
        setLoading(false);
      }
    }
    setOpen((o) => !o);
  }

  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={toggle}
        className="flex items-center gap-1 text-[11px] font-medium text-text-secondary hover:text-foreground"
      >
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        Neden önemli?
      </button>
      {open && (
        <div className="mt-1.5">
          {loading && <p className="text-xs text-text-tertiary">Hesaplanıyor…</p>}
          {reasons?.map((reason, i) => (
            <ProvenanceBlock key={i} type="SYSTEM_INFERENCE" className="mb-1.5">
              {reason.text}
            </ProvenanceBlock>
          ))}
        </div>
      )}
    </div>
  );
}
