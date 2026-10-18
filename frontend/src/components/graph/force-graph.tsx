"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import { Maximize2, Minus, Plus, RotateCcw } from "lucide-react";
import type { EntityGraphData, GraphEdge, GraphNode } from "@/lib/types";
import { CONFIDENCE_COLOR_VAR } from "@/components/provenance/confidence";
import { cn } from "@/lib/utils";

/**
 * Faz 22 — graf görünümü. Bağımlılık EKLENMEDİ, yerleşim burada hesaplanıyor.
 *
 * Gerekçe: bu proje tek kullanıcılı ve local-first; bir çizim kütüphanesi (d3-force,
 * cytoscape) paketin boyutunu ve bakım yüzeyini, çözdüğü problemden fazla büyütürdü.
 * Kuvvet simülasyonu basit bir Fruchterman-Reingold: itme (her düğüm çifti) + çekme
 * (kenarlar) + merkeze doğru hafif bir yerçekimi.
 *
 * **Yerleşim DETERMİNİSTİK.** Başlangıç konumları rastgele değil, düğüm id'sinin hash'inden
 * türetiliyor. Sebep pratik: aynı graf her açılışta farklı yerleşseydi, kullanıcı "dün burada
 * duruyordu" diye hatırladığı düğümü bulamazdı — ve iki ekran görüntüsü karşılaştırılamazdı.
 *
 * **2026-09-09 — üç düzeltme (gerçek kullanımda bulundu).** Graf 5 düğümden 78'e çıkınca
 * çizim okunmaz hale geldi: düğümler üst üste biniyordu ve yapılabilecek hiçbir şey yoktu.
 *   1. **Tuval düğüm sayısıyla büyüyor.** Sabit 900×620, 64 düğüm için tasarlanmıştı; 78
 *      düğüm ve 80 ilişki kenarı aynı alana sıkışınca çekme kuvveti kümeyi bir noktaya
 *      topluyordu. Alan artık düğüm başına sabit bir paya göre hesaplanıyor.
 *   2. **Çakışma çözme pası.** Kuvvet simülasyonu düğümleri "yaklaşık" ayırır ama iki
 *      düğümün ÇİZİLDİĞİ yarıçapı bilmez. Simülasyondan sonra gelen birkaç geçiş, birbirine
 *      yarıçapları toplamından yakın duran çiftleri iterek üst üste binmeyi bitiriyor.
 *   3. **Sürükleme + pan + zoom.** Otomatik yerleşim ne kadar iyi olursa olsun bazı çiftler
 *      örtüşür; kullanıcı elle ayırabilmeli. Sürüklenen düğüm o oturum boyunca sabitlenir
 *      (pin) — determinizm bozulmaz, çünkü başlangıç yerleşimi hâlâ hash'ten türüyor.
 *
 * Erişilebilirlik: SVG dekoratif değil, veri taşıyor. Her düğümün `<title>`ı var, tamamı
 * klavyeyle gezilebiliyor (`tabIndex`) ve graf'ın altında aynı veriyi taşıyan bir metin
 * listesi duruyor — görsel yerleşim tek erişim yolu olmamalı.
 */

// Düğüm başına ayrılan alan. 64 düğümlük eski sabit tuval (900×620 = 558.000 px²) düğüm
// başına ~8.700 px² veriyordu ve o boyutta zaten sıkışıktı; 11.000 ölçülerek seçildi —
// altında çakışma pası çok iş yapmak zorunda kalıyor, üstünde graf gereksiz seyreliyor.
const AREA_PER_NODE = 11_000;
const MIN_WIDTH = 900;
const MIN_HEIGHT = 620;
const ASPECT = 900 / 620;
const ITERATIONS = 300;

// Çakışma çözme: iki düğümün merkezleri arasında en az (r1 + r2 + PAD) olmalı.
const COLLISION_PAD = 14;
const COLLISION_PASSES = 24;

type Positioned = GraphNode & { x: number; y: number };

function nodeRadius(node: GraphNode): number {
  return node.kind === "event" ? 7 : 5 + Math.min(6, node.degree);
}

function canvasSize(count: number): { width: number; height: number } {
  const area = Math.max(MIN_WIDTH * MIN_HEIGHT, count * AREA_PER_NODE);
  const height = Math.sqrt(area / ASPECT);
  return { width: Math.round(height * ASPECT), height: Math.round(height) };
}

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
  const { width: W, height: H } = canvasSize(nodes.length);
  const points: Positioned[] = nodes.map((n) => {
    const seed = seedPosition(n.id);
    return { ...n, x: 40 + seed.x * (W - 80), y: 40 + seed.y * (H - 80) };
  });
  const index = new Map(points.map((p, i) => [p.id, i]));
  const links = edges
    .map((e) => ({ s: index.get(e.source), t: index.get(e.target) }))
    .filter((l): l is { s: number; t: number } => l.s !== undefined && l.t !== undefined);

  const k = Math.sqrt((W * H) / points.length);
  let temperature = W / 8;

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
      dx[i] += (W / 2 - points[i].x) * 0.012;
      dy[i] += (H / 2 - points[i].y) * 0.012;

      const disp = Math.max(0.01, Math.hypot(dx[i], dy[i]));
      const limit = Math.min(disp, temperature);
      points[i].x = Math.min(W - 30, Math.max(30, points[i].x + (dx[i] / disp) * limit));
      points[i].y = Math.min(H - 24, Math.max(24, points[i].y + (dy[i] / disp) * limit));
    }
    temperature *= 0.972;
  }

  // Çakışma çözme. Kuvvet simülasyonu düğümleri "yaklaşık" ayırır ama çizilen yarıçapı
  // bilmez: derecesi yüksek bir düğüm 11px, komşusu 5px yarıçapla çizilir ve merkezleri
  // 12px uzaktaysa daireler birbirinin içine girer. Bu pas tam olarak o örtüşmeyi ölçüp
  // çiftleri birbirinden iterek kapatıyor — yerleşimi bozmadan, yalnızca yerel düzeltme.
  const radii = points.map(nodeRadius);
  for (let pass = 0; pass < COLLISION_PASSES; pass++) {
    let moved = false;
    for (let i = 0; i < points.length; i++) {
      for (let j = i + 1; j < points.length; j++) {
        const min = radii[i] + radii[j] + COLLISION_PAD;
        let vx = points[i].x - points[j].x;
        let vy = points[i].y - points[j].y;
        let dist = Math.hypot(vx, vy);
        if (dist >= min) continue;
        if (dist < 0.01) {
          vx = i < j ? 1 : -1;
          vy = 0;
          dist = 1;
        }
        const push = (min - dist) / 2;
        const ux = (vx / dist) * push;
        const uy = (vy / dist) * push;
        points[i].x = Math.min(W - 30, Math.max(30, points[i].x + ux));
        points[i].y = Math.min(H - 24, Math.max(24, points[i].y + uy));
        points[j].x = Math.min(W - 30, Math.max(30, points[j].x - ux));
        points[j].y = Math.min(H - 24, Math.max(24, points[j].y - uy));
        moved = true;
      }
    }
    if (!moved) break;
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

// Bir işaretçi hareketinin "sürükleme" sayılması için gereken en az mesafe (ekran pikseli).
const DRAG_THRESHOLD_PX = 4;
const ZOOM_MIN = 0.4;
const ZOOM_MAX = 3;
const ZOOM_STEP = 1.25;

export function ForceGraph({
  data,
  onSelect,
}: {
  data: EntityGraphData;
  onSelect?: (node: GraphNode) => void;
}) {
  const [hovered, setHovered] = useState<string | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const { width: W, height: H } = useMemo(() => canvasSize(data.nodes.length), [data.nodes.length]);
  const computed = useMemo(() => layout(data.nodes, data.edges), [data]);

  // Sürüklenmiş düğümlerin konumu. Hesaplanan yerleşimin ÜSTÜNE biniyor, onu değiştirmiyor:
  // "Yerleşimi sıfırla" bu haritayı boşaltmak demek, yeniden hesap değil.
  const [pinned, setPinned] = useState<Record<string, { x: number; y: number }>>({});
  // Graf verisi değiştiğinde taşımalar geçersizdir (düğümler artık başka yerde). Sıfırlama
  // effect'te DEĞİL render sırasında yapılıyor — React'ın belgelenmiş "adjusting state during
  // render" kalıbı; effect olsaydı bir render boyunca eski taşımalar yeni yerleşime uygulanmış
  // olurdu (aynı gerekçe /evidence sayfasında da var).

  const [layoutRef, setLayoutRef] = useState(computed);
  if (layoutRef !== computed) {
    setLayoutRef(computed);
    setPinned({});
  }

  const positions = useMemo(
    () => computed.map((p) => (pinned[p.id] ? { ...p, ...pinned[p.id] } : p)),
    [computed, pinned]
  );
  const byId = useMemo(() => new Map(positions.map((p) => [p.id, p])), [positions]);

  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });

  // Sürükleme durumu ref'te: her pointermove'da state güncellemek 78 düğümlük bir SVG'de
  // gereksiz render zinciri kurardı. Yalnızca taşınan düğümün konumu state'e yazılıyor.
  const suppressClick = useRef(false);
  const drag = useRef<
    | { kind: "node"; id: string; dx: number; dy: number; startX: number; startY: number; moved: boolean }
    | { kind: "pan"; startX: number; startY: number; panX: number; panY: number }
    | null
  >(null);

  /** Ekran koordinatını SVG kullanıcı koordinatına çevirir (zoom/pan hesaba katılarak). */
  const toSvg = useCallback((clientX: number, clientY: number) => {
    const svg = svgRef.current;
    if (!svg) return { x: 0, y: 0 };
    const rect = svg.getBoundingClientRect();
    // viewBox her zaman 0 0 W H; SVG genişliği rect.width. Ölçek ikisinin oranı.
    const scale = W / rect.width;
    return { x: (clientX - rect.left) * scale, y: (clientY - rect.top) * scale };
  }, [W]);

  const worldFromEvent = useCallback(
    (clientX: number, clientY: number) => {
      const p = toSvg(clientX, clientY);
      return { x: (p.x - pan.x) / zoom, y: (p.y - pan.y) / zoom };
    },
    [toSvg, pan, zoom]
  );

  function startNodeDrag(e: React.PointerEvent, node: Positioned) {
    e.stopPropagation();
    (e.target as Element).setPointerCapture?.(e.pointerId);
    const w = worldFromEvent(e.clientX, e.clientY);
    drag.current = {
      kind: "node", id: node.id, dx: node.x - w.x, dy: node.y - w.y,
      startX: e.clientX, startY: e.clientY, moved: false,
    };
  }

  function startPan(e: React.PointerEvent) {
    const p = toSvg(e.clientX, e.clientY);
    drag.current = { kind: "pan", startX: p.x, startY: p.y, panX: pan.x, panY: pan.y };
  }

  function onPointerMove(e: React.PointerEvent) {
    const d = drag.current;
    if (!d) return;
    if (d.kind === "node") {
      // Sürükleme eşiği: tıklama sırasında farenin 1 px kayması düğümü SABİTLİYORDU ve
      // sabitlenmiş düğüme bir daha tıklanamıyordu (onClick sabitlemeye bakıyordu).
      if (!d.moved && Math.hypot(e.clientX - d.startX, e.clientY - d.startY) < DRAG_THRESHOLD_PX) return;
      d.moved = true;
      const w = worldFromEvent(e.clientX, e.clientY);
      setPinned((prev) => ({ ...prev, [d.id]: { x: w.x + d.dx, y: w.y + d.dy } }));
    } else {
      const p = toSvg(e.clientX, e.clientY);
      setPan({ x: d.panX + (p.x - d.startX), y: d.panY + (p.y - d.startY) });
    }
  }

  function endDrag() {
    const d = drag.current;
    // Gerçekten sürüklendiyse ardından gelen click "seç" sayılmamalı.
    suppressClick.current = d?.kind === "node" && d.moved;
    drag.current = null;
  }

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

  function zoomBy(factor: number) {
    setZoom((z) => Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, z * factor)));
  }

  function resetView() {
    setZoom(1);
    setPan({ x: 0, y: 0 });
    setPinned({});
  }

  const pinnedCount = Object.keys(pinned).length;

  return (
    <div className="relative">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        className="w-full touch-none rounded-xl border border-border bg-surface"
        // `img` değil `group`: img rolü alt öğeleri sunumsal yapar ve odaklanabilir düğüm
        // düğmeleri ekran okuyucuya hiç ulaşmıyordu.
        role="group"
        aria-label={`Bilgi graf'ı: ${data.nodes.length} düğüm, ${data.edges.length} kenar`}
        onPointerDown={startPan}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerLeave={endDrag}
      >
        <g transform={`translate(${pan.x} ${pan.y}) scale(${zoom})`}>
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
                      üzerindeyken: hepsini birden yazmak çizimi okunmaz yapıyor. */}
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
              const radius = nodeRadius(node);
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
                  onPointerDown={(e) => startNodeDrag(e, node)}
                  // Sürükleme bittiğinde tıklama sayılmamalı: eşikten fazla taşındıysa
                  // kullanıcı taşımak istemiştir, gezinmek değil.
                  onClick={() => {
                    if (suppressClick.current) {
                      suppressClick.current = false;
                      return;
                    }
                    onSelect?.(node);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onSelect?.(node);
                    }
                  }}
                  className="cursor-grab outline-none active:cursor-grabbing focus-visible:[&>circle]:stroke-ring focus-visible:[&>circle]:stroke-2 focus-visible:[&>rect]:stroke-ring focus-visible:[&>rect]:stroke-2"
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
                      stroke={pinned[node.id] ? "var(--brand-accent)" : "rgba(0,0,0,0.4)"}
                    />
                  ) : (
                    <circle
                      cx={node.x}
                      cy={node.y}
                      r={radius}
                      fill={color}
                      fillOpacity={0.85}
                      stroke={pinned[node.id] ? "var(--brand-accent)" : "rgba(0,0,0,0.4)"}
                    />
                  )}
                  {/* Etiket yalnızca bağlantısı olan ya da üzerine gelinen düğümlerde:
                      tüm etiketleri birden basmak çizimi okunmaz yapıyordu. */}
                  {(node.degree > 0 || hovered === node.id) && (
                    <text
                      x={node.x + radius + 4}
                      y={node.y + 3.5}
                      className={cn(
                        "pointer-events-none text-[10px]",
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
        </g>
      </svg>

      <div className="absolute right-3 top-3 flex items-center gap-1 rounded-lg border border-border bg-surface/90 p-1 backdrop-blur">
        <button
          type="button"
          onClick={() => zoomBy(1 / ZOOM_STEP)}
          aria-label="Uzaklaştır"
          className="rounded p-1.5 text-text-secondary hover:bg-white/10 hover:text-foreground"
        >
          <Minus className="h-4 w-4" />
        </button>
        <span className="min-w-10 text-center text-[11px] tabular-nums text-text-tertiary">
          {Math.round(zoom * 100)}%
        </span>
        <button
          type="button"
          onClick={() => zoomBy(ZOOM_STEP)}
          aria-label="Yakınlaştır"
          className="rounded p-1.5 text-text-secondary hover:bg-white/10 hover:text-foreground"
        >
          <Plus className="h-4 w-4" />
        </button>
        <button
          type="button"
          onClick={resetView}
          aria-label="Görünümü ve taşınan düğümleri sıfırla"
          title="Görünümü ve taşınan düğümleri sıfırla"
          className="rounded p-1.5 text-text-secondary hover:bg-white/10 hover:text-foreground"
        >
          {pinnedCount > 0 ? <RotateCcw className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
        </button>
      </div>

      <p className="mt-2 text-xs text-text-tertiary">
        Düğümleri sürükleyerek ayırabilirsin; boş alanı sürüklemek graf&apos;ı kaydırır.
        Taşınan düğüm vurgulu kenarlıkla işaretlenir ve yerinde kalır
        {pinnedCount > 0 ? ` (${pinnedCount} düğüm taşındı)` : ""}. Bir düğüme gitmek için
        tıkla — taşıdığın düğüm için satırın altındaki listeyi kullan.
      </p>
    </div>
  );
}
