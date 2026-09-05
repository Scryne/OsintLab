"use client";

import { useState } from "react";
import { FileCheck } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
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
import { TypeCombo } from "@/components/forms/type-combo";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";

// Öneri listesi — kural DEĞİL (bkz. TypeCombo).
const EVIDENCE_TYPE_SUGGESTIONS = [
  "fotoğraf", "video", "belge", "uydu görüntüsü", "ekran görüntüsü", "arşiv kaydı", "veri seti",
];

/** Bir Claim'e kanıt bağlama akışı (Faz 10 B4) — "Bitti Kriteri"nin contradicts doğrulama
 * testinin doğrudan UI karşılığı: stance=CONTRADICTS seçilirse confidence.py'nin ceza dalı
 * gerçekten tetiklenir (bkz. backend/app/routers/evidence.py::link_evidence_to_claim). */
export function EvidenceLinkDialog({ claimId, onLinked }: { claimId: string; onLinked: () => void }) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<"existing" | "new">("existing");
  const { data: evidenceList } = useApi(() => api.evidence.list(), [open]);

  const [evidenceId, setEvidenceId] = useState<string | null>(null);
  const [evidenceType, setEvidenceType] = useState(EVIDENCE_TYPE_SUGGESTIONS[0]);
  const [filePath, setFilePath] = useState("");
  const [stance, setStance] = useState<"SUPPORTS" | "CONTRADICTS">("SUPPORTS");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const items = (evidenceList ?? []).map((e) => ({
    id: e.id,
    label: e.evidence_type,
    sublabel: e.file_path ?? undefined,
  }));

  function reset() {
    setEvidenceId(null);
    setFilePath("");
    setStance("SUPPORTS");
    setError(null);
    setMode("existing");
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
      await api.evidence.linkToClaim(targetEvidenceId, claimId, stance);
      toast(`Kanıt bağlandı (${stance})`, "success");
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
          <button
            type="button"
            className="flex items-center gap-1 text-[11px] font-medium text-text-secondary hover:text-foreground"
          >
            <FileCheck aria-hidden className="h-3 w-3" />
            Kanıt bağla
          </button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Bu claim&apos;e kanıt bağla</DialogTitle>
          <DialogDescription>Bu claim&apos;e kanıt bağlar. Bağlanan kanıt confidence&apos;ı yükseltir; duruş, desteklediği yönü söyler.</DialogDescription>
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
              <Label htmlFor="evidence-link-dialog-kanit-1">Kanıt</Label>
              <SearchablePicker id="evidence-link-dialog-kanit-1" items={items} value={evidenceId} onChange={setEvidenceId} placeholder="Kanıt ara…" />
            </div>
          ) : (
            <>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="evidence-type">Tür</Label>
                <TypeCombo
                  id="evidence-type"
                  value={evidenceType}
                  onChange={setEvidenceType}
                  suggestions={EVIDENCE_TYPE_SUGGESTIONS}
                  placeholder="ör. belge, ekran görüntüsü"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="evidence-file-path">Dosya yolu (opsiyonel)</Label>
                <Input
                  id="evidence-file-path"
                  value={filePath}
                  onChange={(e) => setFilePath(e.target.value)}
                  placeholder="ör. C:\…\ekran-goruntusu.png"
                />
              </div>
            </>
          )}

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="evidence-link-dialog-durus-stance-1">Duruş (stance)</Label>
            <Select value={stance} onValueChange={(v) => v && setStance(v as "SUPPORTS" | "CONTRADICTS")}>
              <SelectTrigger id="evidence-link-dialog-durus-stance-1">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="SUPPORTS">SUPPORTS — destekliyor</SelectItem>
                <SelectItem value="CONTRADICTS">CONTRADICTS — çelişiyor</SelectItem>
              </SelectContent>
            </Select>
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
