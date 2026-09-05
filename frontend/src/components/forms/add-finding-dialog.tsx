"use client";

import { useMemo, useState } from "react";
import { Plus } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { SearchablePicker } from "@/components/forms/searchable-picker";
import { useToast } from "@/components/ui/toast";

/**
 * Bir claim'i investigation'ın bulgusu olarak ekler (Faz 11 tarama bulgusu F38).
 *
 * `PUT /investigations/{id}/findings/{claim_id}` arayüzden hiç çağrılmıyordu — yani
 * investigation'a bulgu eklemek mümkün değildi. Findings bölümü yalnızca okunuyordu ve
 * hiçbir zaman dolamazdı; kapanışta VALIDATED_FINDING'e yükselecek bir şey de olmazdı.
 */
export function AddFindingDialog({
  investigationId,
  onAdded,
}: {
  investigationId: string;
  onAdded: () => void;
}) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const { data: claims } = useApi(() => api.claims.list(), [open]);
  const [claimId, setClaimId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const items = useMemo(
    () =>
      (claims ?? []).map((c) => ({
        id: c.id,
        label: c.text.split("\n")[0].slice(0, 64),
        sublabel: `${c.knowledge_state} · %${Math.round(c.confidence * 100)}`,
      })),
    [claims]
  );

  async function submit() {
    if (!claimId) return;
    setSubmitting(true);
    try {
      await api.investigations.addFinding(investigationId, claimId);
      toast("Finding eklendi", "success");
      setClaimId(null);
      setOpen(false);
      onAdded();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Eklenemedi", "error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) setClaimId(null);
      }}
    >
      <DialogTrigger
        render={
          <Button size="sm" variant="outline">
            <Plus aria-hidden className="h-3.5 w-3.5" />
            Finding ekle
          </Button>
        }
      />
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Investigation&apos;a bulgu ekle</DialogTitle>
          <DialogDescription>Bir claim&apos;i bu araştırmanın bulgusu olarak işaretler. Yalnızca doğrulanmış bulgular kapanışta Knowledge Graph&apos;a yükselir.</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="add-finding-dialog-claim-1">Claim</Label>
          <SearchablePicker id="add-finding-dialog-claim-1" items={items} value={claimId} onChange={setClaimId} placeholder="Claim ara…" />
          <p className="text-xs leading-relaxed text-text-tertiary">
            Investigation kapatıldığında yalnızca{" "}
            <span className="font-medium text-foreground">doğrulanmış</span> bilgi durumundaki
            finding&apos;ler kalıcı bilgiye yükselir; geçici notlar yükselmez.
          </p>
        </div>
        <DialogFooter>
          <Button onClick={submit} disabled={submitting || !claimId}>
            {submitting ? "Ekleniyor…" : "Ekle"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
