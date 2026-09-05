"use client";

import { useMemo, useState } from "react";
import { GitMerge } from "lucide-react";
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
 * İki entity'nin aynı şey olduğunu ELLE önerir (Faz 11 dogfooding F29).
 *
 * Neden gerekti: SAME_AS önermenin tek yolu, otomatik tespit edilmiş bir adaya "Öner" demekti.
 * Tespit (`dedup.py`) isim/alias token benzerliğine bakıyor — ve bu, tehdit aktörü alanında
 * yapısal olarak çalışmaz: farklı firmalar aynı gruba bilinçli olarak birbiriyle alakasız
 * isimler verir (APT28 = Fancy Bear = Sofacy = Sednit). "Chaotic Eclipse" ile "INFINITE
 * NIGHTMARE" arasında ortak token yok, skor 0, aday listesi boş — ve kullanıcının hiçbir
 * çıkış yolu yoktu. F23b'nin (lineage'da otomatik tespit tutmayınca elle kurma yolu açıldı)
 * entity tarafındaki birebir kardeşi.
 *
 * Q7 korunuyor: bu uç yalnızca PENDING öneri yaratır, birleştirmeyi yine insan onaylar.
 */
export function SameAsManualDialog({
  entityId,
  onSuggested,
}: {
  entityId: string;
  onSuggested: () => void;
}) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const { data: entities } = useApi(() => (open ? api.entities.list() : Promise.resolve([])), [open]);
  const [otherId, setOtherId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const items = useMemo(
    () =>
      (entities ?? [])
        .filter((e) => e.id !== entityId)
        .map((e) => ({
          id: e.id,
          label: e.name,
          sublabel: e.aliases.length > 0 ? `${e.entity_type} · ${e.aliases.join(", ")}` : e.entity_type,
        })),
    [entities, entityId]
  );

  async function submit() {
    if (!otherId) return;
    setSubmitting(true);
    try {
      await api.entities.suggestSameAs(entityId, otherId);
      toast("Öneri kuyruğa eklendi — aşağıdan onayla", "success");
      setOtherId(null);
      setOpen(false);
      onSuggested();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Öneri eklenemedi", "error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => { setOpen(next); if (!next) setOtherId(null); }}>
      <DialogTrigger
        render={
          <Button size="sm" variant="outline">
            <GitMerge aria-hidden className="h-4 w-4" />
            Elle eşleştir
          </Button>
        }
      />
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Aynı şey olduğunu elle bildir</DialogTitle>
          <DialogDescription>İki entity kaydının aynı şeye ait olduğunu bildirir. Kayıtlar birleştirilmez, aralarında bir eşitlik bağı kurulur.</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="same-as-manual-dialog-ayni-oldug-u-entity-1">Aynı olduğu entity</Label>
          <SearchablePicker id="same-as-manual-dialog-ayni-oldug-u-entity-1" items={items} value={otherId} onChange={setOtherId} placeholder="Entity ara…" />
          <p className="text-xs leading-relaxed text-text-tertiary">
            Otomatik tespit isim benzerliğine bakar; farklı isimler taşıyan aynı aktörü
            (ör. takma adları birbirine benzemeyen tehdit grupları) bulamaz. Bu yol onun için.
            Öneri <span className="font-medium text-foreground">onay bekleyen</span> olarak
            kaydedilir, birleştirmeyi yine sen onaylarsın.
          </p>
        </div>
        <DialogFooter>
          <Button onClick={submit} disabled={submitting || !otherId}>
            {submitting ? "Ekleniyor…" : "Öneri olarak ekle"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
