"use client";

import { useState } from "react";
import { ScanText } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast";

/**
 * Faz 15.2 — bir belgenin seçilen sayfa aralığından Observation üretir.
 *
 * **Neden sayfa aralığı, neden otomatik değil.** Promote, gözlemin ham metnini doğrudan
 * claim metnine çeviriyor. Tüm belge tek gözlem olsaydı 492 sayfalık bir rapor 1,65 milyon
 * karakterlik bir claim üretirdi; her sayfa otomatik gözlem olsaydı tek dosya 492 gözlem
 * yaratıp değerlendirme kuyruğunu tıkardı (Faz 16'nın açmaya çalıştığı darboğaz). Birim
 * bu yüzden kullanıcının seçtiği aralık ve adım açıkça tetikleniyor — Design Principle #7.
 */
export function EvidenceObservationDialog({
  evidenceId,
  pageCount,
  onCreated,
}: {
  evidenceId: string;
  pageCount: number | null;
  onCreated: () => void;
}) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [from, setFrom] = useState("1");
  const [to, setTo] = useState("1");
  const [submitting, setSubmitting] = useState(false);

  const max = pageCount ?? 1;
  const f = Number.parseInt(from, 10);
  const t = Number.parseInt(to, 10);
  const gecerli =
    Number.isFinite(f) && Number.isFinite(t) && f >= 1 && t >= f && t <= max;

  async function submit() {
    if (!gecerli) return;
    setSubmitting(true);
    try {
      const obs = await api.evidence.createObservation(evidenceId, {
        page_from: f,
        page_to: t,
      });
      // Uyarı burada da söyleniyor: kullanıcı gözlemi promote etmeden ÖNCE bilsin.
      if (obs.injection_hits?.length) {
        toast(
          `Gözlem oluşturuldu — dikkat: metinde talimat görünümlü ${obs.injection_hits.length} ifade var`,
          "error"
        );
      } else {
        toast(`Gözlem oluşturuldu (${obs.raw_content.length} karakter)`, "success");
      }
      setOpen(false);
      onCreated();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Gözlem oluşturulamadı", "error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button size="sm" variant="outline" className="h-7 px-2 text-xs">
            <ScanText aria-hidden className="h-3.5 w-3.5" />
            Gözlem üret
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Belgeden gözlem üret</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <p className="text-xs text-text-secondary">
            Seçtiğin sayfaların metni bir Observation olarak sisteme girer ve normal promote
            akışına katılır. Tüm belgeyi tek gözleme çevirmek yerine aralık seçiliyor: promote
            gözlemin metnini doğrudan claim metni yapıyor.
          </p>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="obs-page-from">İlk sayfa</Label>
              <Input
                id="obs-page-from"
                type="number"
                min={1}
                max={max}
                value={from}
                onChange={(e) => setFrom(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="obs-page-to">Son sayfa</Label>
              <Input
                id="obs-page-to"
                type="number"
                min={1}
                max={max}
                value={to}
                onChange={(e) => setTo(e.target.value)}
              />
            </div>
          </div>
          <p className="text-xs text-text-tertiary">
            Belge {max} sayfa. Aralık her iki uçtan dahildir.
            {!gecerli && (
              <span className="text-priority-medium"> Geçerli bir aralık gir (1–{max}).</span>
            )}
          </p>
        </div>
        <DialogFooter>
          <Button onClick={submit} disabled={submitting || !gecerli}>
            {submitting ? "Üretiliyor…" : "Gözlem üret"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
