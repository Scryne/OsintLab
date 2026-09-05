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
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SearchablePicker } from "@/components/forms/searchable-picker";
import { TypeCombo } from "@/components/forms/type-combo";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";

type Stance = "SUPPORTS" | "WEAKENS" | "REFUTES";

// Öneri listesi — kural DEĞİL (bkz. TypeCombo, dogfooding F8).
const EVIDENCE_TYPE_SUGGESTIONS = [
  "fotoğraf", "video", "belge", "uydu görüntüsü", "ekran görüntüsü", "arşiv kaydı", "veri seti",
];

/**
 * Bir hipoteze kanıt bağlar (Faz 11 tarama bulgusu F36; F40 ile tamamlandı).
 *
 * `PUT /hypotheses/{id}/evidence` hipotezin durumunu bağlı kanıtlara göre yeniden hesaplıyor
 * (SUPPORTED/WEAKENED/REFUTED) ama arayüzden hiç çağrılmıyordu — F36'da açıldı.
 *
 * F40: ilk hâli yalnızca VAR OLAN kanıtı bağlıyordu. Graf'ta hiç Evidence olmadığı için
 * diyalog "Sonuç yok" deyip çıkmaz sokağa dönüyordu: kullanıcı kanıtı nereden yaratacağını
 * bilemiyordu (tek yol, bir claim kartındaki ayrı bir diyalogdu). Claim tarafındaki
 * `EvidenceLinkDialog` bu geçişi zaten sunuyordu; asimetri sürtünmeydi.
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
  const { data: evidence } = useApi(() => (open ? api.evidence.list() : Promise.resolve([])), [open]);
  const [mode, setMode] = useState<"existing" | "new">("existing");
  const [evidenceId, setEvidenceId] = useState<string | null>(null);
  const [evidenceType, setEvidenceType] = useState(EVIDENCE_TYPE_SUGGESTIONS[0]);
  const [filePath, setFilePath] = useState("");
  const [stance, setStance] = useState<Stance>("SUPPORTS");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const items = useMemo(
    () =>
      (evidence ?? []).map((e) => ({
        id: e.id,
        label: e.evidence_type,
        sublabel: e.file_path ?? undefined,
      })),
    [evidence]
  );

  function reset() {
    setMode("existing");
    setEvidenceId(null);
    setFilePath("");
    setStance("SUPPORTS");
    setError(null);
  }

  async function submit() {
    setSubmitting(true);
    setError(null);
    try {
      let targetEvidenceId = evidenceId;
      if (mode === "new") {
        const created = await api.evidence.create({
          evidence_type: evidenceType,
          file_path: filePath.trim() || null,
        });
        targetEvidenceId = created.id;
      }
      if (!targetEvidenceId) return;
      const h = await api.investigations.linkHypothesisEvidence(hypothesisId, targetEvidenceId, stance);
      toast(`Kanıt bağlandı — hipotez durumu: ${h.status}`, "success");
      reset();
      setOpen(false);
      onLinked();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bilinmeyen hata");
    } finally {
      setSubmitting(false);
    }
  }

  const canSubmit = mode === "existing" ? !!evidenceId : !!evidenceType;

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) reset();
      }}
    >
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
          <DialogDescription>Bu hipoteze kanıt bağlar ve kanıtın hipotezi desteklediğini mi çürüttüğünü mü belirtir.</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <div className="flex gap-1.5 rounded-lg bg-muted p-1">
            <button
              type="button"
              onClick={() => setMode("existing")}
              className={cn(
                "flex-1 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors",
                mode === "existing" ? "bg-background text-foreground" : "text-text-secondary"
              )}
            >
              Var olan kanıtı bağla
            </button>
            <button
              type="button"
              onClick={() => setMode("new")}
              className={cn(
                "flex-1 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors",
                mode === "new" ? "bg-background text-foreground" : "text-text-secondary"
              )}
            >
              Yeni kanıt oluştur
            </button>
          </div>

          {mode === "existing" ? (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="hypothesis-evidence-dialog-kanit-1">Kanıt</Label>
              <SearchablePicker id="hypothesis-evidence-dialog-kanit-1" items={items} value={evidenceId} onChange={setEvidenceId} placeholder="Kanıt ara…" />
              {items.length === 0 && (
                <p className="text-xs text-text-tertiary">
                  Henüz hiç kanıt yok — <span className="font-medium text-foreground">Yeni kanıt oluştur</span>&apos;a geç.
                </p>
              )}
            </div>
          ) : (
            <>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="hyp-evidence-type">Tür</Label>
                <TypeCombo
                  id="hyp-evidence-type"
                  value={evidenceType}
                  onChange={setEvidenceType}
                  suggestions={EVIDENCE_TYPE_SUGGESTIONS}
                  placeholder="ör. belge, ekran görüntüsü"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="hyp-evidence-path">Dosya yolu (opsiyonel)</Label>
                <Input
                  id="hyp-evidence-path"
                  value={filePath}
                  onChange={(e) => setFilePath(e.target.value)}
                  placeholder="ör. C:\…\rapor.pdf"
                />
              </div>
            </>
          )}

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="hypothesis-evidence-dialog-durus-1">Duruş</Label>
            <Select value={stance} onValueChange={(v) => v && setStance(v as Stance)}>
              <SelectTrigger id="hypothesis-evidence-dialog-durus-1">
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

          {error && <p className="text-sm text-priority-critical-text">{error}</p>}
        </div>
        <DialogFooter>
          <Button onClick={submit} disabled={submitting || !canSubmit}>
            {submitting ? "Bağlanıyor…" : "Bağla"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
