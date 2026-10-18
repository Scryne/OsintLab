"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import type { GraphNode } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorState } from "@/components/ui/state";
import { Skeleton } from "@/components/ui/skeleton";
import { ForceGraph } from "@/components/graph/force-graph";

type Filter = "all" | "connected";

/** Faz 22 — graf görünümü.
 *
 * Faz 8'in "Entity Graph paneli duruyor" notunun YANLIŞ olduğu 2026-09-02'deki v1 denetiminde
 * bulunmuş ve o günden beri kapanmamıştı. Ölçüm (2026-09-08) bunun bir kozmetik eksik
 * olmadığını gösterdi: 109 ilişki adayına karşılık graf'ta 1 kenar vardı ve kurulan kenarın
 * karşılığı hiçbir yerde görünmüyordu — entity sayfasında düz bir liste dışında.
 */
export default function GraphPage() {
  const router = useRouter();
  const { data, error, loading, reload } = useApi(() => api.entities.graph(), []);
  const [filter, setFilter] = useState<Filter>("connected");
  const [selected, setSelected] = useState<GraphNode | null>(null);

  const view = useMemo(() => {
    if (!data) return { nodes: [], edges: [] };
    if (filter === "all") return data;
    // Varsayılan "bağlantılı": tek başına duran düğümler graf'ın kendisini okunmaz yapıyor
    // (58 entity'nin çoğu bir kenara sahip değil). Hepsini görmek isteyen açabilsin.
    const nodes = data.nodes.filter((n) => n.degree > 0);
    const ids = new Set(nodes.map((n) => n.id));
    return { nodes, edges: data.edges.filter((e) => ids.has(e.source) && ids.has(e.target)) };
  }, [data, filter]);

  const relationCount = data?.edges.filter((e) => e.kind === "relation").length ?? 0;
  const isolatedCount = data ? data.nodes.filter((n) => n.degree === 0).length : 0;

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="font-display text-[2rem] font-semibold tracking-tight text-balance text-foreground">
            Graf
          </h1>
          <p className="max-w-2xl text-sm leading-relaxed text-text-secondary">
            Entity&apos;ler (daire) ve olaylar (kare), aralarındaki bağlarla. Kalın çizgi senin
            kurduğun ilişki, soluk çizgi bir olaya karışma, kesik çizgi ise aynı kaydın iki
            adı — aynılık bir ilişki değildir. Bir düğüme gel: yalnızca komşuları kalır.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Button
            size="sm"
            variant={filter === "connected" ? "secondary" : "outline"}
            onClick={() => setFilter("connected")}
            aria-pressed={filter === "connected"}
          >
            Bağlantılılar
          </Button>
          <Button
            size="sm"
            variant={filter === "all" ? "secondary" : "outline"}
            onClick={() => setFilter("all")}
            aria-pressed={filter === "all"}
          >
            Hepsi
          </Button>
        </div>
      </header>

      <div className="flex flex-wrap items-center gap-4 rounded-xl border border-border bg-surface px-4 py-3 text-sm text-text-secondary">
        <span>
          <strong className="tabular-nums text-foreground">{relationCount}</strong> entity ilişkisi
        </span>
        <span>
          <strong className="tabular-nums text-foreground">{data?.edges.length ?? 0}</strong> toplam bağ
        </span>
        <span>
          <strong className="tabular-nums text-foreground">{isolatedCount}</strong> bağlantısız düğüm
        </span>
        <Link
          href="/entities/relations"
          className="ml-auto underline decoration-white/20 underline-offset-2 hover:text-foreground hover:decoration-white/50"
        >
          İlişki adaylarına git →
        </Link>
      </div>

      {loading && <Skeleton className="h-[420px] w-full rounded-xl" />}
      {error && <ErrorState error={error} onRetry={reload} />}
      {!loading && !error && view.nodes.length === 0 && (
        <EmptyState
          title="Graf'ta gösterilecek bağ yok"
          description="İlişki adaylarından ilk bağları kur, ya da bir olaya entity bağla."
        />
      )}

      {!loading && view.nodes.length > 0 && (
        <>
          <ForceGraph
            data={view}
            onSelect={(node) => {
              setSelected(node);
              router.push(node.kind === "event" ? `/events/${node.id}` : `/entities/${node.id}`);
            }}
          />

          {/* Görsel yerleşim tek erişim yolu olmamalı: aynı veri metin olarak da burada.
              Ekran okuyucu ve klavye kullanıcısı için graf bir resim değil, bir liste. */}
          <section>
            <h2 className="mb-2 text-sm font-medium uppercase tracking-wide text-text-tertiary">
              Bağlar ({view.edges.length})
            </h2>
            <ul className="flex flex-col gap-1">
              {view.edges.map((edge, i) => {
                const source = view.nodes.find((n) => n.id === edge.source);
                const target = view.nodes.find((n) => n.id === edge.target);
                if (!source || !target) return null;
                return (
                  <li key={`${edge.source}-${edge.target}-${i}`} className="flex flex-wrap items-center gap-2 text-sm">
                    <Link
                      href={source.kind === "event" ? `/events/${source.id}` : `/entities/${source.id}`}
                      className="text-foreground hover:underline"
                    >
                      {source.label}
                    </Link>
                    <Badge variant="outline">{edge.label}</Badge>
                    <Link
                      href={target.kind === "event" ? `/events/${target.id}` : `/entities/${target.id}`}
                      className="text-foreground hover:underline"
                    >
                      {target.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </section>
        </>
      )}

      {selected && (
        <p className="text-xs text-text-tertiary">Seçilen: {selected.label}</p>
      )}
    </div>
  );
}
