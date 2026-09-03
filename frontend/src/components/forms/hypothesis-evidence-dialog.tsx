"use client";

import { useMemo, useState } from "react";
import { Paperclip } from "lucide-react";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";

type Stance = "SUPPORTS" | "WEAKENS" | "REFUTES";

/**
 * Bir hipoteze kanıt bağlar (Faz 11 tarama bulgusu F36).
 *
 * `PUT /hypotheses/{id}/evidence` backend'de vardı ve hipotezin durumunu (SUPPORTED /
 * WEAKENED / REFUTED) bu bağlara göre yeniden hesaplıyordu — ama arayüzden hiç
 * çağrılmıyordu. Sonuç: hipotez durumu gerçek kullanımda hep UNRESOLVED kalırdı ve
 * `HYPOTHESIS_EVIDENCE` ilişkisi hiç yazılmazdı.
 */
export function HypothesisEvidenceDialog({
  hypothesisId,
  onLinked,
}: {
  hypothesisId: string;
  onLinked: () => void;
}) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const { data: evidence } = useApi(() => api.evidence.list(), [open]);
  const [evidenceId, setEvidenceId] = useState<string | null>(null);
  const [stance, setStance] = useState<Stance>("SUPPORTS");
  const [submitting, setSubmitting] = useState(false);

  const items = useMemo(
    () =>
      (evidence ?? []).map((e) => ({
        id: e.id,
        label: e.evidence_type,
        sublabel: e.file_path ?? undefined,
      })),
    [evidence]
  );

  async function submit() {
    if (!evidenceId) return;
    setSubmitting(true);
    try {
      const h = await api.investigations.linkHypothesisEvidence(hypothesisId, evidenceId, stance);
      toast(`Kanıt bağlandı — hipotez durumu: ${h.status}`, "success");
      setEvidenceId(null);
      setOpen(false);
      onLinked();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Bağlanamadı", "error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => { setOpen(next); if (!next) setEvidenceId(null); }}>
      <DialogTrigger
        render={
          <Button size="sm" variant="ghost">
            <Paperclip aria-hidden className="h-3.5 w-3.5" />
            Kanıt bağla
          </Button>
        }
      />
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Hipoteze kanıt bağla</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label>Kanıt</Label>
            <SearchablePicker items={items} value={evidenceId} onChange={setEvidenceId} placeholder="Kanıt ara…" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Duruş</Label>
            <Select value={stance} onValueChange={(v) => v && setStance(v as Stance)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="SUPPORTS">SUPPORTS — hipotezi destekliyor</SelectItem>
                <SelectItem value="WEAKENS">WEAKENS — zayıflatıyor</SelectItem>
                <SelectItem value="REFUTES">REFUTES — çürütüyor</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-text-tertiary">
              Hipotezin durumu bağlı kanıtlara göre yeniden hesaplanır.
            </p>
          </div>
        </div>
        <DialogFooter>
          <Button onClick={submit} disabled={submitting || !evidenceId}>
            {submitting ? "Bağlanıyor…" : "Bağla"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
