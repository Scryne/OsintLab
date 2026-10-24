"use client";

import { useState } from "react";
import { Grid3x3 } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";

type Stance = "SUPPORTS" | "WEAKENS" | "REFUTES";

// Hücre tıklandıkça döner: boş → destekler → zayıflatır → çürütür → boş.
const NEXT: Record<string, Stance | null> = { "": "SUPPORTS", SUPPORTS: "WEAKENS", WEAKENS: "REFUTES", REFUTES: null };
const CELL: Record<Stance, { mark: string; label: string; cls: string }> = {
  // Duruş bir epistemik durum: confidence ailesinden (destek yeşil, çürütme çelişki tonu).
  SUPPORTS: { mark: "C", label: "tutarlı (destekler)", cls: "text-confidence-supported-text" },
  WEAKENS: { mark: "I", label: "tutarsız (zayıflatır)", cls: "text-priority-medium-text" },
  REFUTES: { mark: "II", label: "çok tutarsız (çürütür)", cls: "text-confidence-contradicted-text" },
};

/** v6 — Rakip Hipotezler Analizi (Heuer'in ACH yöntemi).
 *
 * Satırlar kanıt, sütunlar hipotez. Yöntemin iki kuralı ekranda görünür: (1) en olası hipotez en
 * çok desteklenen değil, EN AZ TUTARSIZ olandır (çürüten 2, zayıflatan 1 puan); (2) her kanıt her
 * hipoteze karşı tartılmalıdır — boş hücreler sayılır ve gösterilir. Bütün hipotezlere aynı
 * duruşu taşıyan kanıt ayırt edici değildir ve soluk gösterilir. */
export function AchMatrix({ investigationId, readOnly, onChanged }: { investigationId: string; readOnly: boolean; onChanged: () => void }) {
  const toast = useToast();
  const { data, reload } = useApi(() => api.investigations.ach(investigationId), [investigationId]);
  const [busy, setBusy] = useState<string | null>(null);

  if (!data || data.hypotheses.length < 2 || data.evidence.length === 0) return null;
  const order = data.ranking;
  const hyps = [...data.hypotheses].sort((a, b) => order.indexOf(a.id) - order.indexOf(b.id));

  async function cycle(evidenceId: string, hypothesisId: string, current: Stance | null) {
    const next = NEXT[current ?? ""];
    setBusy(`${evidenceId}:${hypothesisId}`);
    try {
      if (next) await api.investigations.linkHypothesisEvidence(hypothesisId, evidenceId, next);
      else await api.investigations.unlinkHypothesisEvidence(hypothesisId, evidenceId);
      reload();
      onChanged();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Değiştirilemedi", "error");
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="flex flex-col gap-2">
      <h3 className="flex items-center gap-2 text-sm font-medium text-foreground">
        <Grid3x3 aria-hidden className="h-4 w-4 text-text-tertiary" />
        Rakip hipotezler matrisi (ACH)
      </h3>
      <p className="text-xs text-pretty text-text-secondary">
        En olası hipotez en az tutarsız olandır (soldan sağa sıralı). C tutarlı · I tutarsız · II çok tutarsız.
        {data.unassessed_cells > 0 && ` ${data.unassessed_cells} hücre tartılmadı — her kanıtı her hipoteze karşı değerlendir.`}
        {!readOnly && " Hücreye tıklamak duruşu değiştirir."}
      </p>
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-left text-xs">
          <thead className="bg-white/[0.03] text-text-tertiary">
            <tr>
              <th className="px-2 py-1.5 font-medium">Kanıt</th>
              {hyps.map((h, i) => (
                <th key={h.id} className="min-w-32 px-2 py-1.5 align-bottom font-medium">
                  <span className="line-clamp-2 text-foreground">{i === 0 && "★ "}{h.text}</span>
                  <span className="mt-0.5 block font-mono text-[10px]">
                    tutarsızlık {h.inconsistency} · destek {h.supporting}
                    {h.unassessed > 0 && ` · ${h.unassessed} boş`}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.evidence.map((e) => (
              <tr key={e.id} className={cn("border-t border-border", !e.diagnostic && "opacity-60")}>
                <td className="max-w-56 px-2 py-1.5">
                  <span className="block truncate text-foreground" title={e.name}>{e.name}</span>
                  <span className="text-[10px] text-text-tertiary">{e.evidence_type}{!e.diagnostic && " · ayırt edici değil"}</span>
                </td>
                {hyps.map((h) => {
                  const stance = (e.cells[h.id] ?? null) as Stance | null;
                  const view = stance ? CELL[stance] : null;
                  const key = `${e.id}:${h.id}`;
                  return (
                    <td key={h.id} className="px-2 py-1.5 text-center">
                      <button
                        type="button"
                        disabled={readOnly || busy === key}
                        onClick={() => cycle(e.id, h.id, stance)}
                        aria-label={`${e.name} / ${h.text}: ${view?.label ?? "tartılmadı"}`}
                        className={cn(
                          "h-7 w-10 rounded font-mono text-sm font-semibold",
                          view ? view.cls : "text-text-tertiary",
                          !readOnly && "hover:bg-white/[0.06]"
                        )}
                      >
                        {view?.mark ?? "·"}
                      </button>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
