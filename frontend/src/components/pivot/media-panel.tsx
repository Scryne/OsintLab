"use client";

/* eslint-disable @next/next/no-img-element --
 * Önizleme backend'in yeniden kodladığı yerel bir PNG; next/image'ın uzak görsel optimizasyonu
 * burada anlamsız ve yerel API host'unu yapılandırmaya eklemeyi gerektirirdi. */

import { useState } from "react";
import Link from "next/link";
import { ChevronDown, ChevronRight, ExternalLink, ImageIcon } from "lucide-react";
import { api, API_BASE } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { Facts } from "@/components/pivot/run-summary";
import { SelectorChip } from "@/components/pivot/selector-chip";
import { LoadingState } from "@/components/ui/state";

const IMAGE_EXT = /\.(jpe?g|png|webp|tiff?|gif|bmp|heic|heif)$/i;

export function isImagePath(path: string | null | undefined): boolean {
  return !!path && IMAGE_EXT.test(path);
}

// Ters görsel aramada dosya yükleme sayfaları. Kanıt yerel olduğu için URL'le arama yapılamaz;
// hangi servise yükleneceği kullanıcının kararı (yüklenen dosya o servise gider).
const REVERSE = [
  { name: "Google Lens", url: "https://lens.google.com/" },
  { name: "Yandex Görsel", url: "https://yandex.com/images/" },
  { name: "TinEye", url: "https://tineye.com/" },
  { name: "Bing Visual Search", url: "https://www.bing.com/visualsearch" },
  { name: "Forensically (yerelde çalışır)", url: "https://29a.ch/photo-forensics/" },
];

/** Faz 34 — Kanıt Kasası'nda görsel analizi. Kapalıyken veri çekmez (Frontend kuralı: kapalı
 * paneller istek atmaz). */
export function MediaPanel({ evidenceId }: { evidenceId: string }) {
  const [open, setOpen] = useState(false);
  const { data, loading } = useApi(() => (open ? api.evidence.media(evidenceId) : Promise.resolve(null)), [open, evidenceId]);
  const a = data?.analysis;

  return (
    <div className="mt-3 rounded-lg border border-border">
      <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-text-secondary hover:text-foreground">
        {open ? <ChevronDown aria-hidden className="h-4 w-4" /> : <ChevronRight aria-hidden className="h-4 w-4" />}
        <ImageIcon aria-hidden className="h-4 w-4" />
        Görsel analizi
      </button>
      {open && (
        <div className="flex flex-col gap-4 border-t border-border p-3">
          {loading && <LoadingState />}
          {!loading && !a && <p className="text-sm text-text-tertiary">Görsel henüz işlenmedi ya da dosya bir görsel değil.</p>}
          {a && (
            <>
              <div className="flex flex-col gap-4 md:flex-row">
                <img
                  src={`${API_BASE}/evidence/${evidenceId}/preview`}
                  alt="Kanıt görselinin yeniden kodlanmış önizlemesi"
                  className="max-h-72 w-auto self-start rounded-md border border-border object-contain"
                />
                <div className="flex min-w-0 flex-1 flex-col gap-3">
                  {a.flags.length > 0 && (
                    <ul className="flex flex-col gap-1">
                      {a.flags.map((f: { code: string; text: string }) => (
                        <li
                          key={f.code}
                          className={
                            f.code === "AI_DECLARED" || f.code === "EDITED" || f.code === "MODIFIED_AFTER"
                              ? "text-xs text-priority-medium-text"
                              : "text-xs text-text-secondary"
                          }
                        >
                          {f.text}
                        </li>
                      ))}
                    </ul>
                  )}
                  <Facts
                    rows={[
                      ["Biçim", `${a.image.format} · ${a.image.width}×${a.image.height}${a.image.frames > 1 ? ` · ${a.image.frames} kare` : ""}`],
                      ["Çekim (yerel saat)", a.taken_local],
                      ["dHash", <span key="d" className="font-mono text-xs">{a.hashes.dhash}</span>],
                      ["aHash", <span key="a" className="font-mono text-xs">{a.hashes.ahash}</span>],
                    ]}
                  />
                </div>
              </div>
              {a.gps && (
                <section className="flex flex-col gap-1.5">
                  <h4 className="text-[11px] font-medium uppercase tracking-wide text-text-tertiary">GPS (EXIF)</h4>
                  <div className="flex flex-wrap items-center gap-2 text-sm">
                    <SelectorChip id={`coord:${a.gps.lat.toFixed(6)},${a.gps.lon.toFixed(6)}`} kind="coord" value={`${a.gps.lat.toFixed(6)},${a.gps.lon.toFixed(6)}`} />
                    {a.gps.altitude_m != null && <span className="text-xs text-text-tertiary">irtifa {a.gps.altitude_m} m</span>}
                    {a.gps.direction_deg != null && <span className="text-xs text-text-tertiary">kamera yönü {a.gps.direction_deg}°</span>}
                    {a.gps.timestamp_utc && <span className="font-mono text-xs text-text-tertiary">{a.gps.timestamp_utc}</span>}
                    <Link href={`/tools?lat=${a.gps.lat}&lon=${a.gps.lon}${a.gps.timestamp_utc ? `&at=${encodeURIComponent(a.gps.timestamp_utc)}` : ""}#gunes`} className="text-xs text-brand-accent-text hover:underline">
                      Güneş konumunu kontrol et →
                    </Link>
                  </div>
                </section>
              )}
              {Object.keys(a.exif).length > 0 && (
                <section className="flex flex-col gap-1.5">
                  <h4 className="text-[11px] font-medium uppercase tracking-wide text-text-tertiary">EXIF</h4>
                  <Facts rows={Object.entries(a.exif).map(([k, v]) => [k, String(v)] as [string, React.ReactNode])} />
                </section>
              )}
              {(Object.keys(a.text_chunks).length > 0 || a.xmp?.present) && (
                <section className="flex flex-col gap-1.5">
                  <h4 className="text-[11px] font-medium uppercase tracking-wide text-text-tertiary">Gömülü metin (güvenilmeyen veri)</h4>
                  <Facts
                    rows={[
                      ...Object.entries(a.text_chunks).map(([k, v]) => [k, <span key={k} className="font-mono text-xs">{String(v)}</span>] as [string, React.ReactNode]),
                      ...Object.entries(a.xmp ?? {}).filter(([k]) => k !== "present").map(([k, v]) => [`XMP ${k}`, String(v)] as [string, React.ReactNode]),
                    ]}
                  />
                </section>
              )}
              {data.similar.length > 0 && (
                <section className="flex flex-col gap-1.5">
                  <h4 className="text-[11px] font-medium uppercase tracking-wide text-text-tertiary">Algısal olarak benzer kanıtlar</h4>
                  <ul className="text-xs text-text-secondary">
                    {data.similar.map((s: { evidence_id: string; file_path: string; distance: number }) => (
                      <li key={s.evidence_id} className="font-mono">
                        {s.file_path?.split(/[\\/]/).pop()} · fark {s.distance}/64
                      </li>
                    ))}
                  </ul>
                </section>
              )}
              <section className="flex flex-col gap-1.5">
                <h4 className="text-[11px] font-medium uppercase tracking-wide text-text-tertiary">Ters görsel arama</h4>
                <p className="text-xs text-text-tertiary">
                  Dosyayı <a className="underline" href={`${API_BASE}/evidence/${evidenceId}/file`}>indir</a> ve seçtiğin servise yükle — yüklenen görsel o servise gider.
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {REVERSE.map((r) => (
                    <a key={r.name} href={r.url} target="_blank" rel="noopener noreferrer nofollow" className="inline-flex items-center gap-1 rounded border border-border px-2 py-1 text-xs text-text-secondary hover:border-white/25 hover:text-foreground">
                      {r.name} <ExternalLink aria-hidden className="h-3 w-3" />
                    </a>
                  ))}
                </div>
              </section>
            </>
          )}
        </div>
      )}
    </div>
  );
}
