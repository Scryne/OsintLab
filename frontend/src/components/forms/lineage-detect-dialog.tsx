"use client";

import { useMemo, useState } from "react";
import { Radar } from "lucide-react";
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

type DetectResult = {
  similarity: number;
  shared_agencies: string[];
  is_derived: boolean;
  method: string;
  edge_created: boolean;
};

/**
 * İki claim'i karşılaştırıp aralarında türetme (DERIVED_FROM) olup olmadığını sınar
 * (Faz 11 tarama bulgusu F37).
 *
 * `POST /sources/lineage/detect` backend'de vardı ama arayüzden hiç çağrılmıyordu — Faz 6'nın
 * otomatik tespiti UI'dan tetiklenemiyordu. F23b'de elle lineage kurma yolu açılmıştı;
 * otomatik olan hâlâ erişilemezdi, yani kullanıcı "bu iki haber birbirinden mi türemiş"
 * sorusunu sisteme hiç soramıyordu.
 *
 * Sonucu ham haliyle gösteriyoruz (benzerlik skoru + yöntem) — F23'te öğrenildi: tespit
 * gerçek veride 0.0000 verebiliyor ve kullanıcının bunu görüp elle karar verebilmesi gerekiyor.
 */
export function LineageDetectDialog({ onDetected }: { onDetected: () => void }) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const { data: claims } = useApi(() => api.claims.list(), [open]);
  const [aId, setAId] = useState<string | null>(null);
  const [bId, setBId] = useState<string | null>(null);
  const [result, setResult] = useState<DetectResult | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const items = useMemo(
    () => (claims ?? []).map((c) => ({ id: c.id, label: c.text.split("\n")[0].slice(0, 64) })),
    [claims]
  );
  const bItems = useMemo(() => items.filter((i) => i.id !== aId), [items, aId]);

  async function submit() {
    if (!aId || !bId) return;
    setSubmitting(true);
    try {
      const res = await api.sources.detectLineage(aId, bId);
      setResult(res);
      toast(
        res.edge_created ? "Türetme tespit edildi, lineage kuruldu" : "Türetme sinyali bulunamadı",
        res.edge_created ? "success" : "default"
      );
      if (res.edge_created) onDetected();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Tespit başarısız", "error");
    } finally {
      setSubmitting(false);
    }
  }

  function reset() {
    setAId(null);
    setBId(null);
    setResult(null);
  }

  return (
    <Dialog open={open} onOpenChange={(next) => { setOpen(next); if (!next) reset(); }}>
      <DialogTrigger
        render={
          <Button size="sm" variant="outline">
            <Radar aria-hidden className="h-4 w-4" />
            Türetme sına
          </Button>
        }
      />
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>İki claim arasında türetme sına</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label>Claim A</Label>
            <SearchablePicker items={items} value={aId} onChange={setAId} placeholder="Claim ara…" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Claim B</Label>
            <SearchablePicker items={bItems} value={bId} onChange={setBId} placeholder="Claim ara…" />
          </div>
          {result && (
            <div className="rounded-lg border border-border bg-surface p-3 text-xs leading-relaxed text-text-secondary">
              <p>
                Benzerlik:{" "}
                <span className="font-mono tabular-nums text-foreground">{result.similarity.toFixed(4)}</span> ·
                yöntem: <span className="text-foreground">{result.method}</span>
              </p>
              {result.shared_agencies.length > 0 && (
                <p className="mt-1">Ortak ajans atfı: {result.shared_agencies.join(", ")}</p>
              )}
              <p className="mt-1">
                {result.edge_created
                  ? "Türetilmiş sayıldı — kaynaklar arasına DERIVED_FROM kuruldu."
                  : "Türetme sinyali yok. Metinler birbirini kopyalamıyorsa skor düşük çıkar; aynı olayı bağımsız yazan iki haber böyle görünür. Emin olduğun bir türetme varsa kaynak sayfasından elle kurabilirsin."}
              </p>
            </div>
          )}
        </div>
        <DialogFooter>
          <Button onClick={submit} disabled={submitting || !aId || !bId}>
            {submitting ? "Sınanıyor…" : "Sına"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
