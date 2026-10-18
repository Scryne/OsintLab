"use client";

import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/state";
import { useToast } from "@/components/ui/toast";
import { ConfirmButton } from "@/components/ui/confirm-button";
import { WireframeBurst } from "@/components/ui/wireframe-burst";

export default function SameAsQueuePage() {
  const toast = useToast();
  const { data: pending, error, loading, reload } = useApi(() => api.entities.pendingSameAs(), []);
  const [busyKey, setBusyKey] = useState<string | null>(null);

  async function resolve(fromId: string, toId: string, action: "confirm" | "reject") {
    const key = fromId + toId;
    setBusyKey(key);
    try {
      if (action === "confirm") await api.entities.confirmSameAs(fromId, toId);
      else await api.entities.rejectSameAs(fromId, toId);
      toast(action === "confirm" ? "Eşleşme onaylandı" : "Eşleşme reddedildi", action === "confirm" ? "success" : "default");
      reload();
    } catch (err) {
      toast(err instanceof Error ? err.message : "İşlem başarısız", "error");
    } finally {
      setBusyKey(null);
    }
  }

  return (
    <div className="relative isolate mx-auto flex max-w-3xl flex-col gap-6 overflow-hidden">
      <WireframeBurst spin className="pointer-events-none absolute -right-14 -top-16 -z-10 h-52 w-52 text-white/5" />
      <div>
        <h1 className="font-display text-[2rem] font-semibold tracking-tight text-balance text-foreground">Olası Eşleşmeler</h1>
        <p className="text-sm text-text-secondary">
          Aynı gerçek varlığa ait olabilecek entity çiftleri — sistem hiçbirini kendi başına birleştirmez, onay senin.
        </p>
      </div>

      {loading && <LoadingState />}
      {error && <ErrorState error={error} onRetry={reload} />}
      {!loading && !error && (!pending || pending.length === 0) && (
        <EmptyState
          title="Onay bekleyen eşleşme yok"
          description="Bir entity sayfasındaki 'Olası Eşleşmeler' sekmesinden aday önerebilirsin."
        />
      )}

      <div className="flex flex-col gap-2">
        {pending?.map((p) => {
          const key = p.entity_a_id + p.entity_b_id;
          return (
            <div
              key={key}
              className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4 sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="flex items-center gap-2 text-sm">
                <Link href={`/entities/${p.entity_a_id}`} className="font-medium text-foreground hover:underline">
                  {p.entity_a_name}
                </Link>
                <Badge variant="outline">{p.entity_a_type}</Badge>
                <span className="text-text-tertiary">↔</span>
                <Link href={`/entities/${p.entity_b_id}`} className="font-medium text-foreground hover:underline">
                  {p.entity_b_name}
                </Link>
                <Badge variant="outline">{p.entity_b_type}</Badge>
                <span className="font-mono text-xs tabular-nums text-text-tertiary">%{Math.round(p.confidence * 100)}</span>
              </div>
              <div className="flex shrink-0 items-center gap-1.5">
                <ConfirmButton
                  size="sm"
                  variant="secondary"
                  // "Birleştir?" yanıltıcıydı: kayıtlar birleşmiyor, aralarında bir
                  // eşitlik bağı kuruluyor. Onay düğmesi de eylemi tekrar ediyor.
                  confirmLabel="Aynı kayıt sayılacak, kayıtlar birleşmeyecek"
                  confirmAction="Aynı olduğunu onayla"
                  onConfirm={() => resolve(p.entity_a_id, p.entity_b_id, "confirm")}
                >
                  Aynı
                </ConfirmButton>
                <Button
                  size="sm"
                  variant="destructive"
                  disabled={busyKey === key}
                  onClick={() => resolve(p.entity_a_id, p.entity_b_id, "reject")}
                >
                  Farklı
                </Button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
