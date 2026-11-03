"use client";

import { useMemo, useState } from "react";
import { Link2, Plus } from "lucide-react";
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
import { SearchablePicker } from "@/components/forms/searchable-picker";
import { TypeCombo } from "@/components/forms/type-combo";
import { useToast } from "@/components/ui/toast";
import { entityTypeLabel, entityTypeSuggestions, entityTypeValue } from "@/lib/labels";

const ENTITY_TYPE_SUGGESTIONS = entityTypeSuggestions(["Organization", "Company", "Person"]);

/**
 * Faz 15.3 — bir belge metadata alanını graf'taki bir Entity'ye bağlar.
 *
 * **Öneri sistem, karar insan** (Design Principle #7). `/Author: Joint Task Force` bir kuruma
 * benziyor olabilir; ama hangi Entity olduğu — ya da hiçbiri olmadığı — bir yargı. Sistem
 * yalnızca ada göre muhtemel eşleşmeleri öne alıyor, bağı kullanıcı kuruyor.
 *
 * Alan değeri graf'ta karşılığı olmayabilir (ilk kez görülen bir kurum); o yüzden "yeni
 * entity oluştur" yolu aynı diyalogda. Aksi halde kullanıcı Entity'ler sayfasına gidip
 * geri dönmek zorunda kalırdı ve akış orada kopardı.
 */
export function FingerprintLinkDialog({
  evidenceId,
  field,
  value,
  onLinked,
}: {
  evidenceId: string;
  field: string;
  value: string;
  onLinked: () => void;
}) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const { data: entities } = useApi(
    () => (open ? api.entities.list() : Promise.resolve(null)),
    [open]
  );
  const [entityId, setEntityId] = useState<string | null>(null);
  const [yeniMod, setYeniMod] = useState(false);
  const [yeniTur, setYeniTur] = useState(ENTITY_TYPE_SUGGESTIONS[0]);
  const [submitting, setSubmitting] = useState(false);

  // Ada göre muhtemel eşleşmeler üste alınıyor — otomatik seçilmiyor, yalnızca sıralanıyor.
  const items = useMemo(() => {
    const v = value.trim().toLowerCase();
    const hepsi = (entities ?? []).map((e) => ({
      id: e.id,
      label: e.name,
      sublabel: entityTypeLabel(e.entity_type),
      benzer:
        v.length > 2 &&
        (e.name.toLowerCase().includes(v) || v.includes(e.name.toLowerCase())),
    }));
    return [...hepsi].sort((a, b) => Number(b.benzer) - Number(a.benzer));
  }, [entities, value]);

  const onerilen = items.find((i) => i.benzer);

  async function submit() {
    setSubmitting(true);
    try {
      let hedef = entityId;
      if (yeniMod) {
        const yeni = await api.entities.create({ entity_type: entityTypeValue(yeniTur), name: value.trim() });
        hedef = yeni.id;
      }
      if (!hedef) return;
      await api.evidence.linkFingerprint(evidenceId, hedef, field);
      toast(`${field} alanı varlığa bağlandı`, "success");
      setOpen(false);
      setEntityId(null);
      setYeniMod(false);
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
          <Button size="sm" variant="outline" className="h-6 px-1.5 text-[11px]">
            <Link2 aria-hidden className="h-3 w-3" />
            Varlığa bağla
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Üst veri alanını varlığa bağla</DialogTitle>
          <DialogDescription>Belgenin üst veri alanından çıkan kişi ya da kurumu bir varlığa bağlar.</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          {/* Q22 — bu değer belgeyi kim ürettiyse onun yazdığı metindir. Sınır burada da
              görünür kalıyor: bağlanan şeyin ham veri olduğu unutulmasın. */}
          <div className="rounded-md border border-dashed border-border bg-black/30 p-2">
            <p className="font-mono text-[10px] uppercase tracking-wide text-text-tertiary">
              güvenilmeyen içerik · üst veri:{field}
            </p>
            <p className="mt-1 break-words font-mono text-xs text-foreground">{value}</p>
          </div>

          {!yeniMod && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="fingerprint-link-dialog-mevcut-entity-1">Mevcut varlık</Label>
              <SearchablePicker
                id="fingerprint-link-dialog-mevcut-entity-1"
                items={items.map(({ id, label, sublabel }) => ({ id, label, sublabel }))}
                value={entityId}
                onChange={setEntityId}
                placeholder="Varlık ara…"
                emptyText="Henüz varlık yok"
              />
              {onerilen && !entityId && (
                <p className="text-xs text-text-tertiary">
                  Ada göre olası eşleşme: <span className="text-foreground">{onerilen.label}</span> — kararı sen ver.
                </p>
              )}
            </div>
          )}

          {yeniMod && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="fp-new-type">Yeni varlık türü</Label>
              <TypeCombo
                id="fp-new-type"
                value={yeniTur}
                onChange={setYeniTur}
                suggestions={ENTITY_TYPE_SUGGESTIONS}
                placeholder="ör. Organization"
              />
              <p className="text-xs text-text-tertiary">
                &quot;{value}&quot; adıyla yeni bir varlık oluşturulup bu alana bağlanacak.
              </p>
            </div>
          )}

          <button
            type="button"
            onClick={() => setYeniMod((v) => !v)}
            className="self-start text-xs text-text-tertiary underline decoration-white/20 underline-offset-2 hover:text-foreground"
          >
            {yeniMod ? "Mevcut bir varlık seç" : (
              <span className="inline-flex items-center gap-1">
                <Plus aria-hidden className="h-3 w-3" />
                Grafta karşılığı yok — yeni varlık oluştur
              </span>
            )}
          </button>
        </div>
        <DialogFooter>
          <Button onClick={submit} disabled={submitting || (!yeniMod && !entityId)}>
            {submitting ? "Bağlanıyor…" : "Bağla"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
