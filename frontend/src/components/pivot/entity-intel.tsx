"use client";

import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { EmptyState } from "@/components/ui/state";
import { SkeletonRows } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { EnrichmentPanel } from "@/components/pivot/enrichment-panel";
import { SelectorChip } from "@/components/pivot/selector-chip";
import { DorkList, ToolLinks } from "@/components/pivot/tool-links";

/** Faz 31 — entity sayfasındaki "Altyapı ve zenginleştirme" sekmesi.
 *
 * Kurum düzeyindeki modüller (Wikidata, GLEIF, OFAC, GDELT) bir ADA bakar; sonuçlar adaydır.
 * Wikidata'nın önerdiği resmi site gibi bir seçici, kullanıcı "bağla" deyince eklenir ve
 * entity'ye bağlanır — sistem bunu kendi başına yapmaz (Design Principle #7). */
export function EntityIntel({ entityId, name }: { entityId: string; name: string }) {
  const toast = useToast();
  const { data: selectors, loading, reload } = useApi(() => api.selectors.forEntity(entityId), [entityId]);

  async function suggest(_kind: string, value: string) {
    try {
      const sel = await api.selectors.create(value, `${name} için öneriden eklendi`);
      await api.selectors.linkEntity(sel.id, entityId, "Wikidata önerisi, kullanıcı onayladı");
      toast(`${value} eklendi ve ${name} ile bağlandı`, "success");
      reload();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Eklenemedi", "error");
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <section className="flex flex-col gap-2">
        <h3 className="text-sm font-medium text-foreground">Bağlı seçiciler</h3>
        {loading ? (
          <SkeletonRows count={2} />
        ) : selectors?.length ? (
          <div className="flex flex-wrap gap-1.5">
            {selectors.map((s) => (
              <SelectorChip key={s.id} id={s.id} kind={s.kind} value={s.value} />
            ))}
          </div>
        ) : (
          <EmptyState
            title="Bu entity'ye bağlı altyapı yok"
            description="Bir seçicinin sayfasındaki 'Entity bağları' sekmesinden ya da aşağıdaki Wikidata önerisinden bağlayabilirsin."
          />
        )}
      </section>
      <section className="flex flex-col gap-2">
        <h3 className="text-sm font-medium text-foreground">Kurum zenginleştirme</h3>
        <EnrichmentPanel targetId={`entity:${entityId}`} onSuggest={suggest} />
      </section>
      <section className="flex flex-col gap-2">
        <h3 className="text-sm font-medium text-foreground">Dış araçlar</h3>
        <ToolLinks kind="entity" value={name} />
      </section>
      <section className="flex flex-col gap-2">
        <h3 className="text-sm font-medium text-foreground">Arama operatörleri</h3>
        <DorkList kind="entity" value={name} />
      </section>
    </div>
  );
}
