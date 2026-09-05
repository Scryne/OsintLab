"use client";

import { useMemo, useState } from "react";
import { GitCompareArrows } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { SearchablePicker } from "@/components/forms/searchable-picker";
import { useToast } from "@/components/ui/toast";

/**
 * İki mevcut Claim arasına sonradan çelişki kurar (Faz 11 dogfooding F26).
 *
 * Çelişki şimdiye kadar yalnızca claim OLUŞTURULURKEN kurulabiliyordu, ve toplanan veriden
 * Claim'e giden tek yol olan promote bu alanı hiç göndermiyordu. Sonuç: collector'dan gelen
 * hiçbir claim çelişkili işaretlenemiyor, confidence.py'nin çelişki dalı ve CONTRADICTED
 * durumu gerçek boru hattında hiç tetiklenmiyordu.
 *
 * Sonradan kurabilmek sadece bir onarım yolu değil, normal akış: çelişen ikinci haber, ilk
 * claim kaydedildikten günler sonra çıkıyor.
 */
export function ClaimContradictDialog({
  entityClaimIds,
  onLinked,
}: {
  entityClaimIds: string[];
  onLinked: () => void;
}) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const { data: claims } = useApi(() => api.claims.list(), [open]);
  const [claimId, setClaimId] = useState<string | null>(null);
  const [otherId, setOtherId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const label = (text: string) => text.split("\n")[0].slice(0, 64);

  // Bu entity'nin claim'leri başa: çelişki neredeyse her zaman aynı konu içinde çıkıyor.
  const items = useMemo(() => {
    const all = claims ?? [];
    const mine = all.filter((c) => entityClaimIds.includes(c.id));
    const rest = all.filter((c) => !entityClaimIds.includes(c.id));
    return [
      ...mine.map((c) => ({ id: c.id, label: label(c.text), sublabel: "bu kayda ait" })),
      ...rest.map((c) => ({ id: c.id, label: label(c.text), sublabel: c.knowledge_state })),
    ];
  }, [claims, entityClaimIds]);

  const otherItems = useMemo(() => items.filter((i) => i.id !== claimId), [items, claimId]);

  async function submit() {
    if (!claimId || !otherId) return;
    setSubmitting(true);
    try {
      await api.claims.addContradiction(claimId, otherId);
      toast("Çelişki kaydedildi — iki claim de CONTRADICTED", "success");
      setClaimId(null);
      setOtherId(null);
      setOpen(false);
      onLinked();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Çelişki kurulamadı", "error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) {
          setClaimId(null);
          setOtherId(null);
        }
      }}
    >
      <DialogTrigger
        render={
          <Button size="sm" variant="outline">
            <GitCompareArrows aria-hidden className="h-4 w-4" />
            Çelişki kur
          </Button>
        }
      />
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>İki claim arasında çelişki kur</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="claim-contradict-dialog-claim-1">Claim</Label>
            <SearchablePicker id="claim-contradict-dialog-claim-1" items={items} value={claimId} onChange={setClaimId} placeholder="Claim ara…" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="claim-contradict-dialog-c-elis-tig-i-claim-2">Çeliştiği claim</Label>
            <SearchablePicker id="claim-contradict-dialog-c-elis-tig-i-claim-2" items={otherItems} value={otherId} onChange={setOtherId} placeholder="Claim ara…" />
          </div>
          <p className="rounded-lg border border-priority-high/30 bg-priority-high/5 px-3 py-2 text-xs leading-relaxed text-text-secondary">
            İkisi de <span className="font-medium text-foreground">CONTRADICTED</span> durumuna geçer, çelişki{" "}
            <span className="font-medium text-foreground">UNRESOLVED</span> kaydedilir.{" "}
            <span className="font-medium text-foreground">Hiçbir claim silinmez</span> — metinler
            değişmez, aralarına yalnızca bir ilişki eklenir.
          </p>
        </div>
        <DialogFooter>
          <Button onClick={submit} disabled={submitting || !claimId || !otherId || claimId === otherId}>
            {submitting ? "Kaydediliyor…" : "Çelişkiyi kaydet"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
