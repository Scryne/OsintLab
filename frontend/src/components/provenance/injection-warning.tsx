import { ShieldAlert } from "lucide-react";
import type { InjectionHit } from "@/lib/types";

/**
 * Faz 15.2 (Q22) — toplanan içerikte bulunan talimat-görünümlü ifadelerin gösterimi.
 *
 * **Neden ekranda açık bir SINIR çiziliyor.** `.claude/CLAUDE.md`'deki kural, güvenilmeyen
 * içeriğin her zaman görünür bir sınır içinde sunulmasını söylüyor. Bu bileşen o kuralın
 * arayüzdeki karşılığı: alıntı bir çerçevenin içinde, monospace ve "GÜVENİLMEYEN İÇERİK"
 * başlığıyla duruyor — okuyan kişi (insan ya da bir sonraki ajan) bunun sistemin kendi
 * metni değil, dışarıdan gelmiş ham veri olduğunu tek bakışta görsün.
 *
 * **Bu bir engelleme değil.** İçerik yine de sisteme giriyor ve promote edilebiliyor;
 * asıl koruma, hiçbir katmanın bu metni komut olarak yürütmemesi. Uyarının tek işi
 * kullanıcıyı haberdar etmek — Faz 11'in tekrar eden dersi, sistemin fark ettiği şeyi
 * söyleyebilmesiydi.
 */
export function InjectionWarning({
  hits,
  compact = false,
}: {
  hits: InjectionHit[] | null | undefined;
  compact?: boolean;
}) {
  if (!hits || hits.length === 0) return null;

  return (
    <div className="rounded-lg border border-priority-high/40 bg-priority-high/5 p-3">
      <div className="flex items-start gap-2">
        <ShieldAlert aria-hidden className="mt-0.5 h-4 w-4 shrink-0 text-priority-high-text" />
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium text-priority-high-text">
            {hits.length === 1
              ? "Bu içerikte talimat görünümlü bir ifade var"
              : `Bu içerikte talimat görünümlü ${hits.length} ifade var`}
          </p>
          <p className="mt-0.5 text-xs text-text-secondary">
            Açık kaynaktan gelen metin hiçbir zaman komut olarak işlenmez — aşağıdaki alıntı
            yalnızca bilgi içindir. İçerik engellenmedi, olduğu gibi saklandı.
          </p>

          {!compact && (
            <div className="mt-2 flex flex-col gap-2">
              {hits.slice(0, 4).map((h, i) => (
                <div
                  key={`${h.where}-${i}`}
                  className="overflow-hidden rounded-md border border-dashed border-border bg-black/30"
                >
                  <div className="border-b border-dashed border-border px-2 py-1 font-mono text-[10px] uppercase tracking-wide text-text-tertiary">
                    güvenilmeyen içerik · {h.where}
                  </div>
                  <p className="overflow-x-auto whitespace-pre-wrap break-words px-2 py-1.5 font-mono text-[11px] leading-relaxed text-text-secondary">
                    {h.snippet}
                  </p>
                </div>
              ))}
              {hits.length > 4 && (
                <p className="text-[11px] text-text-tertiary">
                  …ve {hits.length - 4} ifade daha.
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
