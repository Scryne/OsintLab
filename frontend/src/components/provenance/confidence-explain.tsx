"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { api } from "@/lib/api";
import type { ClaimExplain } from "@/lib/types";
import { ProvenanceBlock } from "@/components/provenance/provenance-label";
import { ConfidenceBadge } from "@/components/provenance/confidence";

/**
 * Faz 18 yan onarımı — "bu skor nereden geliyor?"
 *
 * `GET /claims/{id}/explain` Faz 2'den beri vardı ve arayüzde **hiç çağrılmıyordu**: skorun
 * kırılımı yalnızca API'ye elle sorulunca görülebiliyordu. Auditability'yi merkeze alan bir
 * projede (Q4: "neden bu confidence?" her zaman cevaplanabilmeli) bu bir boşluktu.
 *
 * Aynı turda backend'e eklenen `corroborated_by` bu ekranın asıl parçası: skor artık
 * doğrulayan claim'leri ve kaynaklarını da söylüyor. `counts_for_independence: false`
 * satırları özellikle önemli — "üç kaynak doğruluyor ama bağımsızlık neden yarım?"
 * sorusunun cevabı orada (Q6: aynı köke inen iki kaynak tek bağımsız kaynak sayılır).
 *
 * Q15 etiketi SYSTEM_INFERENCE: bu kırılım sistemin kendi hesabı, kaynağın iddiası değil.
 */
const ROW_LABEL: Record<keyof ClaimExplain["weights"], string> = {
  source_quality: "Kaynak kalitesi",
  independence: "Bağımsızlık",
  evidence: "Kanıt",
  corroboration: "Doğrulama",
};

export function ConfidenceExplainDisclosure({ claimId }: { claimId: string }) {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<ClaimExplain | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Panel ÖNCE açılır, veri sonra gelir: eskiden `open` istek bitince değişiyordu, yani
  // "Hesaplanıyor…" hiç görünmüyor, yavaş bir istekte ikinci tıklama ikinci isteği başlatıp
  // paneli kapalı bırakıyordu.
  async function toggle() {
    const next = !open;
    setOpen(next);
    if (!next || data !== null || loading) return;
    setLoading(true);
    setError(null);
    try {
      setData(await api.claims.explain(claimId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kırılım alınamadı");
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
        Bu skor nereden geliyor?
      </button>
      {open && (
        <div className="mt-1.5">
          {loading && <p className="text-xs text-text-tertiary">Hesaplanıyor…</p>}
          {error && <p className="text-xs text-priority-critical-text">{error}</p>}
          {data && (
            <ProvenanceBlock type="SYSTEM_INFERENCE">
              <dl className="flex flex-col gap-1 text-[11px]">
                {(Object.keys(ROW_LABEL) as (keyof ClaimExplain["weights"])[]).map((key) => (
                  <div key={key} className="flex items-center gap-2">
                    <dt className="w-28 shrink-0 text-text-secondary">{ROW_LABEL[key]}</dt>
                    <dd className="flex min-w-0 flex-1 items-center gap-2">
                      {/* Ölçek çubuğu dekoratif: sayı zaten yanında yazıyor, ekran okuyucu
                          ikisini birden okumasın diye aria-hidden. */}
                      <span aria-hidden className="h-1 w-24 overflow-hidden rounded-full bg-white/10">
                        <span
                          className="block h-full rounded-full bg-white/50"
                          style={{ width: `${Math.round(data[key] * 100)}%` }}
                        />
                      </span>
                      <span className="font-mono tabular-nums text-text-secondary">
                        {data[key].toFixed(2)} × {data.weights[key].toFixed(2)}
                      </span>
                    </dd>
                  </div>
                ))}
                <div className="mt-1 flex items-center gap-2 border-t border-border pt-1">
                  <dt className="w-28 shrink-0 text-text-secondary">Toplam</dt>
                  <dd className="font-mono tabular-nums text-foreground">{data.confidence.toFixed(4)}</dd>
                </div>
              </dl>

              <div className="mt-2">
                <p className="text-[11px] font-medium text-text-secondary">
                  Doğrulayan claim&apos;ler ({data.corroborated_by.length})
                </p>
                {data.corroborated_by.length === 0 ? (
                  <p className="mt-1 text-[11px] text-text-tertiary">
                    Bu iddiayı başka hiçbir claim doğrulamıyor — confidence&apos;ın %40&apos;ı kaynaktan
                    gelir, kalan %60 ancak doğrulama, bağımsızlık ve kanıtla açılır.
                  </p>
                ) : (
                  <ul className="mt-1 flex flex-col gap-1.5">
                    {data.corroborated_by.map((c) => (
                      <li key={c.claim_id} className="flex flex-col gap-0.5">
                        <span className="text-[11px] text-pretty text-text-secondary">
                          {c.text.split("\n")[0]}
                        </span>
                        <span className="flex flex-wrap items-center gap-2 text-[11px] text-text-tertiary">
                          <ConfidenceBadge state={c.knowledge_state} confidence={c.confidence} />
                          {c.source_name}
                          {!c.counts_for_independence && (
                            <span className="text-priority-high-text">
                              bağımsızlığa sayılmıyor — daha önce sayılmış bir kaynakla aynı kökten
                            </span>
                          )}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              {/* Faz 26: kanıt satırı bugüne kadar hep 0.0000 idi, gösterecek bir kaynağı da
                  yoktu. Artık sıfır olmayabildiğine göre "hangi kanıt" sorusu da cevaplanmalı —
                  yoksa skor yükselir ama açıklanabilirliği düşerdi. Arşiv kayıtlarında
                  durumu da yazıyoruz: bir arşiv skora ancak doğrulanmışsa girer. */}
              <div className="mt-2">
                <p className="text-[11px] font-medium text-text-secondary">
                  Kanıt ({data.evidence_from.length})
                </p>
                {data.evidence_from.length === 0 ? (
                  <p className="mt-1 text-[11px] text-text-tertiary">
                    Bu iddiaya bağlı kanıt yok. Kaynak sayfasının arşiv kopyası varsa, canlı
                    sayfaya karşı doğrulandığında skora girer — Kaynak Arşivi sayfasına bak.
                  </p>
                ) : (
                  <ul className="mt-1 flex flex-col gap-1">
                    {data.evidence_from.map((e) => (
                      <li key={e.evidence_id} className="flex flex-wrap items-center gap-2 text-[11px] text-text-tertiary">
                        <span className="text-text-secondary">{e.evidence_type}</span>
                        {e.archive_status && <span>{e.archive_status.toLowerCase()}</span>}
                        {e.content_hash && (
                          <span className="font-mono">sha256:{e.content_hash.slice(0, 12)}</span>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </ProvenanceBlock>
          )}
        </div>
      )}
    </div>
  );
}
