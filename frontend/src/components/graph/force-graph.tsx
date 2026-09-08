"use client";

import { useMemo, useRef, useState } from "react";
import type { EntityGraphData, GraphEdge, GraphNode } from "@/lib/types";
import { CONFIDENCE_COLOR_VAR } from "@/components/provenance/confidence";
import { cn } from "@/lib/utils";

/**
 * Faz 22 — graf görünümü. Bağımlılık EKLENMEDİ, yerleşim burada hesaplanıyor.
 *
 * Gerekçe: bu proje tek kullanıcılı ve local-first; 64 düğüm / 10 kenarlık bir graf için
 * bir çizim kütüphanesi (d3-force, cytoscape) paketin boyutunu ve bakım yüzeyini, çözdüğü
 * problemden fazla büyütürdü. Kuvvet simülasyonu 200 adımlık basit bir Fruchterman-Reingold:
 * itme (her düğüm çifti) + çekme (kenarlar) + merkeze doğru hafif bir yerçekimi.
 *
 * **Yerleşim DETERMİNİSTİK.** Başlangıç konumları rastgele değil, düğüm id'sinin hash'inden
 * türetiliyor. Sebep pratik: aynı graf her açılışta farklı yerleşseydi, kullanıcı "dün burada
 * duruyordu" diye hatırladığı düğümü bulamazdı — ve iki ekran görüntüsü karşılaştırılamazdı.
 *
 * Erişilebilirlik: SVG dekoratif değil, veri taşıyor. Her düğümün `<title>`ı var, tamamı
 * klavyeyle gezilebiliyor (`tabIndex`) ve graf'ın altında aynı veriyi taşıyan bir metin
 * listesi duruyor — görsel yerleşim tek erişim yolu olmamalı.
 */

const WIDTH = 900;
const HEIGHT = 620;
const ITERATIONS = 260;

type Positioned = GraphNode & { x: number; y: number };

/** Düğüm id'sinden 0-1 arası deterministik iki sayı — rastgele başlangıcın yerine. */
function seedPosition(id: string): { x: number; y: number } {
  let h1 = 2166136261;
  let h2 = 5381;
  for (let i = 0; i < id.length; i++) {
    h1 = Math.imul(h1 ^ id.charCodeAt(i), 16777619) >>> 0;
    h2 = ((h2 << 5) + h2 + id.charCodeAt(i)) >>> 0;
  }
  return { x: (h1 % 1000) / 1000, y: (h2 % 1000) / 1000 };
}

function layout(nodes: GraphNode[], edges: GraphEdge[]): Positioned[] {
  if (nodes.length === 0) return [];
  const points: Positioned[] = nodes.map((n) => {
    const seed = seedPosition(n.id);
    return { ...n, x: 40 + seed.x * (WIDTH - 80), y: 40 + seed.y * (HEIGHT - 80) };
  });
  const index = new Map(points.map((p, i) => [p.id, i]));
  const links = edges
    .map((e) => ({ s: index.get(e.source), t: index.get(e.target) }))
    .filter((l): l is { s: number; t: number } => l.s !== undefined && l.t !== undefined);

  const area = WIDTH * HEIGHT;
  const k = Math.sqrt(area / points.length);
  let temperature = WIDTH / 8;

  for (let step = 0; step < ITERATIONS; step++) {
    const dx = new Array(points.length).fill(0);
    const dy = new Array(points.length).fill(0);

    // İtme: her çift birbirini uzağa iter, yakınlaştıkça sertleşir.
    for (let i = 0; i < points.length; i++) {
      for (let j = i + 1; j < points.length; j++) {
        let vx = points[i].x - points[j].x;
        let vy = points[i].y - points[j].y;
        let dist = Math.hypot(vx, vy);
        if (dist < 0.01) {
          // Üst üste düşen iki düğüm: id sırasına göre sabit bir yöne it (deterministik).
          vx = i < j ? 0.5 : -0.5;
          vy = i < j ? -0.5 : 0.5;
          dist = 0.71;
        }
        const force = (k * k) / dist;
        dx[i] += (vx / dist) * force;
        dy[i] += (vy / dist) * force;
        dx[j] -= (vx / dist) * force;
        dy[j] -= (vy / dist) * force;
      }
    }

    // Çekme: kenarla bağlı düğümler birbirine yaklaşır.
    for (const link of links) {
      const vx = points[link.s].x - points[link.t].x;
      const vy = points[link.s].y - points[link.t].y;
      const dist = Math.max(0.01, Math.hypot(vx, vy));
      const force = (dist * dist) / k;
      dx[link.s] -= (vx / dist) * force;
      dy[link.s] -= (vy / dist) * force;
      dx[link.t] += (vx / dist) * force;
      dy[link.t] += (vy / dist) * force;
    }

    for (let i = 0; i < points.length; i++) {
      // Hafif merkez çekimi: bağlantısız düğümler kenara savrulup görünmez olmasın.
      dx[i] += (WIDTH / 2 - points[i].x) * 0.012;
      dy[i] += (HEIGHT / 2 - points[i].y) * 0.012;

      const disp = Math.max(0.01, Math.hypot(dx[i], dy[i]));
      const limit = Math.min(disp, temperature);
      points[i].x = Math.min(WIDTH - 30, Math.max(30, points[i].x + (dx[i] / disp) * limit));
      points[i].y = Math.min(HEIGHT - 24, Math.max(24, points[i].y + (dy[i] / disp) * limit));
    }
    temperature *= 0.972;
  }
  return points;
}

const EDGE_STYLE: Record<GraphEdge["kind"], { stroke: string; dash?: string }> = {
  // İlişki türü kullanıcının kurduğu bağ — en belirgin çizgi.
  relation: { stroke: "rgba(255,255,255,0.45)" },
  // Olaya karışma otomatik türetilebilen bir bağ; daha soluk.
  involved_in: { stroke: "rgba(255,255,255,0.18)" },
  // Aynılık bir ilişki DEĞİL; kesik çizgi bunu görsel olarak da ayırıyor.
  same_as: { stroke: "rgba(255,255,255,0.3)", dash: "4 4" },
};

export function ForceGraph({
  data,
  onSelect,
}: {
  data: EntityGraphData;
  onSelect?: (node: GraphNode) => void;
}) {
  const [hovered, setHovered] = useState<string | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const positions = useMemo(() => layout(data.nodes, data.edges), [data]);
  const byId = useMemo(() => new Map(positions.map((p) => [p.id, p])), [positions]);

  const neighbours = useMemo(() => {
    const map = new Map<string, Set<string>>();
    for (const edge of data.edges) {
      if (!map.has(edge.source)) map.set(edge.source, new Set());
      if (!map.has(edge.target)) map.set(edge.target, new Set());
      map.get(edge.source)!.add(edge.target);
      map.get(edge.target)!.add(edge.source);
    }
    return map;
  }, [data.edges]);

  function dimmed(id: string) {
    if (!hovered) return false;
    return hovered !== id && !neighbours.get(hovered)?.has(id);
  }

  return (
    <svg
      ref={svgRef}
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      className="w-full rounded-xl border border-border bg-surface"
      role="img"
      aria-label={`Bilgi graf'ı: ${data.nodes.length} düğüm, ${data.edges.length} kenar`}
    >
      <g>
        {data.edges.map((edge, i) => {
          const s = byId.get(edge.source);
          const t = byId.get(edge.target);
          if (!s || !t) return null;
          const style = EDGE_STYLE[edge.kind];
          const faded = hovered ? hovered !== edge.source && hovered !== edge.target : false;
          return (
            <g key={`${edge.source}-${edge.target}-${edge.kind}-${i}`} opacity={faded ? 0.15 : 1}>
              <line
                x1={s.x}
                y1={s.y}
                x2={t.x}
                y2={t.y}
                stroke={style.stroke}
                strokeWidth={edge.kind === "relation" ? 1.6 : 1}
                strokeDasharray={style.dash}
              />
              {/* Kenar etiketi yalnızca kullanıcının kurduğu ilişkilerde ve yalnızca fare
                  üzerindeyken: 10 kenarda bile hepsini birden yazmak çizimi okunmaz yapıyor. */}
              {edge.kind === "relation" && (hovered === edge.source || hovered === edge.target) && (
                <text
                  x={(s.x + t.x) / 2}
                  y={(s.y + t.y) / 2 - 4}
                  textAnchor="middle"
                  className="fill-text-secondary text-[10px]"
                >
                  {edge.label}
                </text>
              )}
            </g>
          );
        })}
      </g>
      <g>
        {positions.map((node) => {
          const radius = node.kind === "event" ? 7 : 5 + Math.min(6, node.degree);
          const color =
            node.kind === "event"
              ? CONFIDENCE_COLOR_VAR[node.knowledge_state ?? "OBSERVED"]
              : node.degree > 0
                ? "var(--brand-accent)"
                : "rgba(255,255,255,0.35)";
          return (
            <g
              key={node.id}
              opacity={dimmed(node.id) ? 0.2 : 1}
              tabIndex={0}
              role="button"
              aria-label={`${node.label} — ${node.kind === "event" ? "olay" : node.entity_type}, ${node.degree} bağ`}
              onMouseEnter={() => setHovered(node.id)}
              onMouseLeave={() => setHovered(null)}
              onFocus={() => setHovered(node.id)}
              onBlur={() => setHovered(null)}
              onClick={() => onSelect?.(node)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onSelect?.(node);
                }
              }}
              className="cursor-pointer outline-none focus-visible:[&>circle]:stroke-ring focus-visible:[&>circle]:stroke-2"
            >
              <title>{node.label}</title>
              {node.kind === "event" ? (
                // Olaylar kare, entity'ler daire: renk körü bir kullanıcı için de ayrım kalsın.
                <rect
                  x={node.x - radius}
                  y={node.y - radius}
                  width={radius * 2}
                  height={radius * 2}
                  rx={2}
                  fill={color}
                  fillOpacity={0.85}
                  stroke="rgba(0,0,0,0.4)"
                />
              ) : (
                <circle cx={node.x} cy={node.y} r={radius} fill={color} fillOpacity={0.85} stroke="rgba(0,0,0,0.4)" />
              )}
              {/* Etiket yalnızca bağlantısı olan ya da üzerine gelinen düğümlerde: 64 etiketi
                  birden basmak çizimi okunmaz yapıyordu. */}
              {(node.degree > 0 || hovered === node.id) && (
                <text
                  x={node.x + radius + 4}
                  y={node.y + 3.5}
                  className={cn(
                    "text-[10px]",
                    hovered === node.id ? "fill-foreground" : "fill-text-secondary"
                  )}
                >
                  {node.label.length > 26 ? `${node.label.slice(0, 26)}…` : node.label}
                </text>
              )}
            </g>
          );
        })}
      </g>
    </svg>
  );
}
