"use client";

import { useState } from "react";
import { GitBranch, X } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import type { Source } from "@/lib/types";
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
import { Input } from "@/components/ui/input";
import { SearchablePicker } from "@/components/forms/searchable-picker";
import { useToast } from "@/components/ui/toast";

/**
 * Bir Source'un DERIVED_FROM lineage zincirini gösterir ve elle bağ kurmayı sağlar.
 *
 * Faz 11 (dogfooding F23): otomatik tespit (`POST /sources/lineage/detect`) kelime n-gram
 * benzerliğine dayanıyor. Faz 6 spike'ı metni BİREBİR kopyalayan yayıncılarla doğrulanmıştı
 * (containment 0.44-0.62). Gerçek AI/LLM haberlerinde ise TechCrunch ve The Verge aynı olayı
 * kendi cümleleriyle yazdığı için similarity 0.0 çıkıyor — türetme var ama tespit edilemiyor.
 * Design Principle #7 gereği son karar zaten insanda; bu ekran o kararı graf'a yazıyor.
 */
export function LineageDialog({
  source,
  allSources,
  onChanged,
}: {
  source: Source;
  allSources: Source[];
  /** Faz 13: kaynak detay sayfası lineage'i diyalogun dışında da gösteriyor — bağ kurulunca
   * ya da kaldırılınca oradaki zincirin de tazelenmesi gerekiyor. */
  onChanged?: () => void;
}) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const { data: lineage, reload } = useApi(
    () => (open ? api.sources.lineage(source.id) : Promise.resolve(null)),
    [open, source.id]
  );
  const [upstreamId, setUpstreamId] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const candidates = allSources
    .filter((s) => s.id !== source.id)
    .map((s) => ({ id: s.id, label: s.name, sublabel: s.source_type }));

  async function link() {
    if (!upstreamId) return;
    setSubmitting(true);
    try {
      const res = await api.sources.linkDerivedFrom(source.id, {
        upstream_source_id: upstreamId,
        note: note.trim() || null,
      });
      toast(`Lineage kuruldu · ${res.recomputed_claims} claim yeniden hesaplandı`, "success");
      setUpstreamId(null);
      setNote("");
      reload();
      onChanged?.();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Bağlanamadı", "error");
    } finally {
      setSubmitting(false);
    }
  }

  // Faz 13: lineage ucu artık tam bir Source değil, {id, name, url, depth} döndürüyor —
  // burada zaten yalnızca id ve name kullanılıyordu.
  async function unlink(upstream: { id: string; name: string }) {
    try {
      await api.sources.unlinkDerivedFrom(source.id, upstream.id);
      toast("Lineage bağı kaldırıldı", "default");
      reload();
      onChanged?.();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Kaldırılamadı", "error");
    }
  }

  const isRoot = lineage ? lineage.independent_root_id === source.id : null;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button size="sm" variant="outline" className="self-start">
            <GitBranch aria-hidden className="h-4 w-4" />
            Lineage
          </Button>
        }
      />
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{source.name} — kaynak bağımsızlığı</DialogTitle>
        </DialogHeader>

        <div className="flex max-h-[60vh] flex-col gap-4 overflow-y-auto pr-1">
          <div className="rounded-lg border border-border bg-surface p-3 text-sm">
            {isRoot === null ? (
              <p className="text-text-tertiary">Yükleniyor…</p>
            ) : isRoot ? (
              <p className="text-foreground">
                Bu kaynak <span className="font-medium">bağımsız kök</span> — bilinen bir üst
                kaynaktan türetilmemiş.
              </p>
            ) : (
              <p className="text-foreground">
                Bu kaynak başka bir kaynaktan türetilmiş; confidence hesabında bağımsız tanık
                sayılmaz.
              </p>
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            {/* Bunlar bir form kontrolünü değil bir listeyi başlıklıyor; `<Label>`
                buraya ait değil (hiçbir zaman bir alana bağlanamaz, ekran okuyucuya
                yanlış vaatte bulunur). Düz başlık metni doğru eleman. */}
            <p className="text-sm font-medium leading-none">Türetildiği kaynaklar (upstream)</p>
            {!lineage || lineage.ancestors.length === 0 ? (
              <p className="text-xs text-text-tertiary">Yok.</p>
            ) : (
              <ul className="flex flex-col gap-1">
                {lineage.ancestors.map((a) => (
                  <li
                    key={a.id}
                    className="flex items-center justify-between gap-2 rounded-md border border-border bg-surface px-2.5 py-1.5 text-sm"
                  >
                    <span className="text-foreground">{a.name}</span>
                    <button
                      type="button"
                      onClick={() => unlink(a)}
                      aria-label={`${a.name} bağını kaldır`}
                      className="text-text-tertiary hover:text-priority-critical-text"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            <p className="text-sm font-medium leading-none">Bu kaynaktan türeyenler (downstream)</p>
            {!lineage || lineage.descendants.length === 0 ? (
              <p className="text-xs text-text-tertiary">Yok.</p>
            ) : (
              <ul className="flex flex-col gap-1">
                {lineage.descendants.map((d) => (
                  <li
                    key={d.id}
                    className="rounded-md border border-border bg-surface px-2.5 py-1.5 text-sm text-foreground"
                  >
                    {d.name}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="flex flex-col gap-1.5 border-t border-border pt-4">
            <Label htmlFor="lineage-dialog-bu-kaynak-s-undan-tu-retilmi-1">Bu kaynak şundan türetilmiş:</Label>
            <SearchablePicker
              id="lineage-dialog-bu-kaynak-s-undan-tu-retilmi-1"
              items={candidates}
              value={upstreamId}
              onChange={setUpstreamId}
              placeholder="Kaynak ara…"
            />
            <Label htmlFor="lineage-note" className="mt-1">
              Gerekçe (opsiyonel)
            </Label>
            <Input
              id="lineage-note"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="ör. aynı duyuruyu aktarıyor, orijinal kaynağa atıf var"
            />
            <p className="text-xs text-text-tertiary">
              Elle kurulan bağ graf&apos;ta <span className="font-mono">MANUAL</span> olarak
              işaretlenir — kararı sistemin mi insanın mı verdiği ayırt edilebilir kalır.
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button onClick={link} disabled={submitting || !upstreamId}>
            {submitting ? "Bağlanıyor…" : "Türetme bağını kur"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
