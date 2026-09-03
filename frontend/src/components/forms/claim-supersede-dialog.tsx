"use client";

import { useMemo, useState } from "react";
import { History } from "lucide-react";
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
 * Var olan bir claim'in, var olan başka bir claim'in yerini aldığını sonradan bildirir
 * (Faz 11 dogfooding F45).
 *
 * F26'da bilerek ertelenmişti; Oturum 4'te gerçek bir engel oldu. Veride gerçek bir supersede
 * vardı — OpenAI Ağustos'ta eşiği "dışlayamıyoruz" diyor, 1 Eylül'de doğruluyor — ama Eylül
 * claim'i graf'ta zaten vardı. Supersede'i yalnızca claim OLUŞTURULURKEN beyan ettiren
 * tasarım, gerçek araştırma sırasına uymuyor: yeni bilgi çoğu zaman eskisi kaydedildikten
 * sonra çıkıyor, bazen de eskisi sonradan kaydediliyor.
 *
 * Eski claim SİLİNMEZ — yalnızca geçerlilik penceresi (`valid_to`) kapanır, ve kapanış anı
 * kayıt zamanı değil yeni claim'in `valid_from`'udur (F44).
 */
export function ClaimSupersedeDialog({
  entityClaimIds,
  onLinked,
}: {
  entityClaimIds: string[];
  onLinked: () => void;
}) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const { data: claims } = useApi(() => api.claims.list(), [open]);
  const [newerId, setNewerId] = useState<string | null>(null);
  const [olderId, setOlderId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const label = (text: string) => text.split("\n")[0].slice(0, 60);

  const items = useMemo(() => {
    const all = claims ?? [];
    const tarih = (v: string | null) => (v ? new Date(v).toLocaleDateString("tr-TR") : "tarihsiz");
    const mine = all.filter((c) => entityClaimIds.includes(c.id));
    const rest = all.filter((c) => !entityClaimIds.includes(c.id));
    return [
      ...mine.map((c) => ({ id: c.id, label: label(c.text), sublabel: `bu kayda ait · ${tarih(c.valid_from)}` })),
      ...rest.map((c) => ({ id: c.id, label: label(c.text), sublabel: tarih(c.valid_from) })),
    ];
  }, [claims, entityClaimIds]);

  const olderItems = useMemo(() => items.filter((i) => i.id !== newerId), [items, newerId]);

  async function submit() {
    if (!newerId || !olderId) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.claims.addSupersede(newerId, olderId);
      toast("Supersede kaydedildi — eski claim arşiv oldu", "success");
      setNewerId(null);
      setOlderId(null);
      setOpen(false);
      onLinked();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Kaydedilemedi");
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
          setNewerId(null);
          setOlderId(null);
          setError(null);
        }
      }}
    >
      <DialogTrigger
        render={
          <Button size="sm" variant="outline">
            <History aria-hidden className="h-4 w-4" />
            Supersede
          </Button>
        }
      />
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Bir claim&apos;in yerini aldığını bildir</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label>Yeni claim (yerini alan)</Label>
            <SearchablePicker items={items} value={newerId} onChange={setNewerId} placeholder="Claim ara…" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Eski claim (yerini bırakan)</Label>
            <SearchablePicker items={olderItems} value={olderId} onChange={setOlderId} placeholder="Claim ara…" />
          </div>
          <p className="rounded-lg border border-priority-high/30 bg-priority-high/5 px-3 py-2 text-xs leading-relaxed text-text-secondary">
            Eski claim <span className="font-medium text-foreground">silinmez</span> — geçerlilik
            penceresi kapanır ve arşiv kaydı olarak işaretlenir. Kapanış anı, yeni claim&apos;in
            geçerli olmaya başladığı tarihtir (kayıt anı değil).
          </p>
          {error && <p className="text-sm text-priority-critical">{error}</p>}
        </div>
        <DialogFooter>
          <Button onClick={submit} disabled={submitting || !newerId || !olderId || newerId === olderId}>
            {submitting ? "Kaydediliyor…" : "Kaydet"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
