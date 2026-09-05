"use client";

import { useState } from "react";
import { Link2 } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { SearchablePicker } from "@/components/forms/searchable-picker";
import { useToast } from "@/components/ui/toast";

/** Kanıt → Claim yönü. `EvidenceLinkDialog` aynı kenarı ters yönden kurar (bir claim'in
 * sayfasından kanıt seçerek); Kanıt Kasası'nda ihtiyaç bunun tersi: elindeki kanıtı hangi
 * iddiaya bağlayacağını seçmek. Aynı uç, aynı stance semantiği — CONTRADICTS seçilirse
 * confidence.py'nin ceza dalı gerçekten tetiklenir. */
export function EvidenceClaimLinkDialog({
  evidenceId,
  onLinked,
}: {
  evidenceId: string;
  onLinked: () => void;
}) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const { data: claims } = useApi(() => (open ? api.claims.list() : Promise.resolve(null)), [open]);
  const [claimId, setClaimId] = useState<string | null>(null);
  const [stance, setStance] = useState<"SUPPORTS" | "CONTRADICTS">("SUPPORTS");
  const [submitting, setSubmitting] = useState(false);

  const items = (claims ?? []).map((c) => ({
    id: c.id,
    // Claim.text bileşik bir alan; başlık ilk satır (F46 — ortak kalıp).
    label: c.text.split("\n").find((l) => l.trim()) ?? c.text,
    sublabel: `${c.knowledge_state} · %${Math.round(c.confidence * 100)}`,
  }));

  async function submit() {
    if (!claimId) return;
    setSubmitting(true);
    try {
      await api.evidence.linkToClaim(evidenceId, claimId, stance);
      toast(stance === "SUPPORTS" ? "Kanıt claim'i destekliyor olarak bağlandı" : "Kanıt claim'i çürütüyor olarak bağlandı", "success");
      setOpen(false);
      setClaimId(null);
      onLinked();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Bağlanamadı", "error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button size="sm" variant="outline" className="h-7 px-2 text-xs">
            <Link2 aria-hidden className="h-3.5 w-3.5" />
            Claim&apos;e bağla
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Kanıtı bir claim&apos;e bağla</DialogTitle>
          <DialogDescription>Bu kanıtı bir claim&apos;e bağlar ve kanıtın claim&apos;i desteklediğini mi yoksa çürüttüğünü mü belirtir.</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="evidence-claim-link-dialog-claim-1">Claim</Label>
            <SearchablePicker
              id="evidence-claim-link-dialog-claim-1"
              items={items}
              value={claimId}
              onChange={setClaimId}
              placeholder="Claim ara…"
              emptyText="Henüz claim yok"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="evidence-claim-link-dialog-durus-1">Duruş</Label>
            <Select value={stance} onValueChange={(v) => v && setStance(v as "SUPPORTS" | "CONTRADICTS")}>
              <SelectTrigger id="evidence-claim-link-dialog-durus-1">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="SUPPORTS">Destekliyor</SelectItem>
                <SelectItem value="CONTRADICTS">Çürütüyor</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-text-tertiary">
              Çürütüyor seçilirse claim&apos;in confidence&apos;ı ceza alır ve yeniden hesaplanır.
            </p>
          </div>
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
