"use client";

import { useState } from "react";
import { Tags } from "lucide-react";
import { api } from "@/lib/api";
import type { Entity } from "@/lib/types";
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
import { useToast } from "@/components/ui/toast";

/**
 * Bir entity'nin alias'larını düzenler (Faz 11 dogfooding F30).
 *
 * `aliases` şemada ve API'de (POST + PATCH) baştan beri vardı, ama frontend hiçbir yerde
 * yazmıyordu: oluşturma formunda alan yoktu, düzenleme yolu hiç yoktu. Yani alias'lar
 * pratikte HER ZAMAN boştu — ve `dedup.py` eşleşme skorunu `name + aliases` token'ları
 * üzerinden hesapladığı için, tespitin alias yarısı gerçek veride hiç çalışmamıştı.
 *
 * OSINT'te asıl sinyal tam olarak burada: "Chaotic Eclipse, also known as INFINITE NIGHTMARE"
 * cümlesindeki bilgi alias alanına yazılırsa otomatik tespit çalışmaya başlar.
 */
export function EntityAliasesDialog({ entity, onSaved }: { entity: Entity; onSaved: () => void }) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState(entity.aliases.join(", "));
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    setSubmitting(true);
    try {
      const aliases = value
        .split(",")
        .map((a) => a.trim())
        .filter(Boolean);
      await api.entities.update(entity.id, {
        entity_type: entity.entity_type,
        name: entity.name,
        aliases,
      });
      toast(aliases.length > 0 ? `${aliases.length} alias kaydedildi` : "Alias'lar temizlendi", "success");
      setOpen(false);
      onSaved();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Kaydedilemedi", "error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) setValue(entity.aliases.join(", "));
      }}
    >
      <DialogTrigger
        render={
          <Button size="sm" variant="outline">
            <Tags aria-hidden className="h-4 w-4" />
            Alias&apos;lar
          </Button>
        }
      />
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{entity.name} — alias&apos;lar</DialogTitle>
          <DialogDescription>Bu entity&apos;nin bilinen diğer adlarını yönetir. Alias&apos;lar arama ve eşleştirmede kullanılır.</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="entity-aliases">Alias&apos;lar (virgülle ayır)</Label>
          <Input
            id="entity-aliases"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="INFINITE NIGHTMARE, MSNightmare, Nightmare-Eclipse"
          />
          <p className="text-xs leading-relaxed text-text-tertiary">
            Alias&apos;lar olası eşleşme tespitine girdi olur — aynı aktörün farklı isimleri
            buraya yazılırsa sistem eşleşmeyi kendi bulabilir.
          </p>
        </div>
        <DialogFooter>
          <Button onClick={submit} disabled={submitting}>
            {submitting ? "Kaydediliyor…" : "Kaydet"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
