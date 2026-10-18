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
/** `detail` gevşek tipli (Record<string, unknown>) — çelişki listesini güvenle çıkarır. */
function contradictingClaims(reason: WhyMattersReason): { id: string; excerpt: string }[] {
  const raw = reason.detail?.contradicting_claims;
  if (!Array.isArray(raw)) return [];
  return raw.filter(
    (c): c is { id: string; excerpt: string } =>
      typeof c === "object" && c !== null && typeof (c as { id?: unknown }).id === "string"
  );
}

export function WhyMattersDisclosure({ claimId }: { claimId: string }) {
  const [open, setOpen] = useState(false);
  const [reasons, setReasons] = useState<WhyMattersReason[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Panel ÖNCE açılır (bkz. ConfidenceExplainDisclosure): "Hesaplanıyor…" görünür olsun ve
  // yavaş istekte ikinci tıklama ikinci isteği başlatmasın. Hata artık yutulmuyor.
  async function toggle() {
    const next = !open;
    setOpen(next);
    if (!next || reasons !== null || loading) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.claims.whyMatters(claimId);
      setReasons(res.reasons);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gerekçe alınamadı");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={toggle}
        aria-expanded={open}
        className="flex items-center gap-1 text-[11px] font-medium text-text-secondary hover:text-foreground"
      >
        {open ? <ChevronDown aria-hidden className="h-3 w-3" /> : <ChevronRight aria-hidden className="h-3 w-3" />}
        Neden önemli?
      </button>
      {open && (
        <div className="mt-1.5">
          {loading && <p className="text-xs text-text-tertiary">Hesaplanıyor…</p>}
          {error && <p className="text-xs text-priority-critical-text">{error}</p>}
          {reasons?.map((reason, i) => (
            <ProvenanceBlock key={i} type="SYSTEM_INFERENCE" className="mb-1.5">
              {reason.text}
              {/* Faz 11 (F27): "neyle çelişiyor" araştırmanın asıl sorusu — çelişen
                  claim'lerin metni burada listeleniyor. Link VERİLMEDİ: tek bir claim'in
                  detay sayfası (`/claims/[id]`) henüz yok, link kırık olurdu (bkz. F20). */}
              {reason.code === "CONTRADICTED" && contradictingClaims(reason).length > 0 && (
                <ul className="mt-1.5 flex list-disc flex-col gap-1 pl-4 text-[11px] text-text-secondary">
                  {contradictingClaims(reason).map((c) => (
                    <li key={c.id}>{c.excerpt}</li>
                  ))}
                </ul>
              )}
            </ProvenanceBlock>
          ))}
        </div>
      )}
    </div>
  );
}
