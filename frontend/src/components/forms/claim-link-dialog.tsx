"use client";

import { useMemo, useState } from "react";
import { Link2 } from "lucide-react";
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
 * Mevcut bir Claim'i bu entity'ye bağlar (Faz 11 dogfooding F16).
 *
 * Promote ekranında "İlgili" alanı atlanırsa claim graf'ta yalıtık kalıyordu ve onarmanın
 * hiçbir yolu yoktu: claims router'ında güncelleme/silme ucu yoktu, promote ise idempotent
 * olduğu için ikinci denemede 409 veriyordu. Bağlantısız claim'ler listenin başında gösterilir.
 */
export function ClaimLinkDialog({ entityId, onLinked }: { entityId: string; onLinked: () => void }) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const { data: claims } = useApi(() => (open ? api.claims.list() : Promise.resolve([])), [open]);
  const [claimId, setClaimId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const items = useMemo(() => {
    const all = claims ?? [];
    const unlinked = all.filter((c) => !c.about_entity_id && !c.about_event_id);
    const others = all.filter((c) => c.about_entity_id !== entityId && (c.about_entity_id || c.about_event_id));
    const label = (text: string) => text.split("\n")[0].slice(0, 64);
    return [
      ...unlinked.map((c) => ({ id: c.id, label: label(c.text), sublabel: "bağlantısız" })),
      ...others.map((c) => ({ id: c.id, label: label(c.text), sublabel: "başka bir kayda bağlı" })),
    ];
  }, [claims, entityId]);

  async function submit() {
    if (!claimId) return;
    setSubmitting(true);
    try {
      await api.claims.updateAbout(claimId, { about_entity_id: entityId });
      toast("Claim bu entity'ye bağlandı", "success");
      setClaimId(null);
      setOpen(false);
      onLinked();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Bağlanamadı", "error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => { setOpen(next); if (!next) setClaimId(null); }}>
      <DialogTrigger
        render={
          <Button size="sm" variant="outline">
            <Link2 aria-hidden className="h-4 w-4" />
            Mevcut claim&apos;i bağla
          </Button>
        }
      />
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Claim&apos;i bu entity&apos;ye bağla</DialogTitle>
          <DialogDescription>Bir claim&apos;i bu entity ile ilişkilendirir. Claim&apos;in metni değişmez, yalnızca neyle ilgili olduğu düzeltilir.</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="claim-link-dialog-claim-1">Claim</Label>
          <SearchablePicker id="claim-link-dialog-claim-1" items={items} value={claimId} onChange={setClaimId} placeholder="Claim ara…" />
          <p className="text-xs text-text-tertiary">
            Bağlantısız claim&apos;ler listenin başında. Claim&apos;in metni değişmez, yalnızca neyle
            ilgili olduğu düzeltilir.
          </p>
        </div>
        <DialogFooter>
          <Button onClick={submit} disabled={submitting || !claimId}>
            {submitting ? "Bağlanıyor…" : "Bağla"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
