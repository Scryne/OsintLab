"use client";

import { useMemo } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import type { EntityGraphData, GraphNode } from "@/lib/types";
import { KIND_LABELS, selectorHref, type SelectorKind } from "@/lib/types-pivot";
import { ForceGraph } from "@/components/graph/force-graph";
import { EmptyState, ErrorState } from "@/components/ui/state";
import { Skeleton } from "@/components/ui/skeleton";

/** Faz 31 — seçicinin pivot komşuluğu. Mevcut graf bileşeni yeniden kullanılıyor: seçici daire,
 * bağlı entity kare; zenginleştirmenin kurduğu pivot düz çizgi, kullanıcının kurduğu "bu
 * altyapı şu kuruma ait" bağı soluk çizgi. */
export function PivotGraphView({ selectorId }: { selectorId: string }) {
  const router = useRouter();
  const { data, error, loading, reload } = useApi(() => api.selectors.graph(selectorId, 2), [selectorId]);

  const graph: EntityGraphData = useMemo(() => {
    if (!data) return { nodes: [], edges: [] };
    const degree = new Map<string, number>();
    for (const e of data.edges) {
      degree.set(e.source, (degree.get(e.source) ?? 0) + 1);
      degree.set(e.target, (degree.get(e.target) ?? 0) + 1);
    }
    const nodes: GraphNode[] = data.nodes.map((n) => ({
      id: n.id,
      kind: n.type === "entity" ? "event" : "entity",
      label: n.value.length > 34 ? `${n.value.slice(0, 32)}…` : n.value,
      entity_type: n.type === "entity" ? (n.entity_type ?? "Entity") : KIND_LABELS[n.kind as SelectorKind],
      degree: degree.get(n.id) ?? 0,
      knowledge_state: null,
      confidence: null,
    }));
    return {
      nodes,
      edges: data.edges.map((e) => ({
        source: e.source,
        target: e.target,
        kind: e.relation === "belongs_to" ? "involved_in" : "relation",
        label: e.relation,
      })),
    };
  }, [data]);

  if (loading) return <Skeleton className="h-80 w-full" />;
  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (!data || data.nodes.length <= 1) {
    return (
      <EmptyState
        title="Henüz pivot yok"
        description="Zenginleştirme modülleri (DNS, sertifika, RDAP, InternetDB…) çalıştıkça bu seçiciden diğerlerine giden bağlar burada belirir."
      />
    );
  }
  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs text-text-tertiary">
        {data.nodes.length} düğüm · {data.edges.length} bağ · iki adım{data.truncated ? " · 150 düğümde kesildi" : ""}. Bir düğüme
        tıkla: o seçicinin sayfasına geçersin.
      </p>
      <ForceGraph
        data={graph}
        onSelect={(node) => {
          if (node.id.startsWith("entity:")) router.push(`/entities/${node.id.slice(7)}`);
          else router.push(selectorHref(node.id));
        }}
      />
    </div>
  );
}
