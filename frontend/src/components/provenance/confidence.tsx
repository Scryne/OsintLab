import { cn } from "@/lib/utils";
import type { KnowledgeState } from "@/lib/types";

// Confidence Spectrum — bkz. docs/Design.md "Farklılaştırıcı Detay". Bu sıralama bilinçli:
// soğuktan (belirsiz) sıcağa (yüksek güven) bir rampa; CONTRADICTED rampanın DIŞINDA.
export const CONFIDENCE_ORDER: KnowledgeState[] = [
  "UNKNOWN",
  "OBSERVED",
  "REPORTED",
  "SUPPORTED",
  "CORROBORATED",
  "HIGH_CONFIDENCE",
];

export const CONFIDENCE_COLOR_VAR: Record<KnowledgeState, string> = {
  UNKNOWN: "var(--confidence-unknown)",
  OBSERVED: "var(--confidence-observed)",
  REPORTED: "var(--confidence-reported)",
  SUPPORTED: "var(--confidence-supported)",
  CORROBORATED: "var(--confidence-corroborated)",
  HIGH_CONFIDENCE: "var(--confidence-high_confidence)",
  CONTRADICTED: "var(--confidence-contradicted)",
};

/** Metin rengi zeminden/kenarlıktan AYRI bir token — bkz. globals.css'teki kontrast notu.
 * Nokta ve kenarlık ham rampa rengini kullanmaya devam eder (dekoratif + UI bileşeni,
 * 3:1 eşiğini geçiyor); sadece `text-xs` metin okunur tona çekildi. Rampa sırası ve
 * CONTRADICTED'ın rampa dışında durması aynen korunuyor. */
export const CONFIDENCE_TEXT_VAR: Record<KnowledgeState, string> = {
  UNKNOWN: "var(--confidence-unknown-text)",
  OBSERVED: "var(--confidence-observed-text)",
  REPORTED: "var(--confidence-reported-text)",
  SUPPORTED: "var(--confidence-supported-text)",
  CORROBORATED: "var(--confidence-corroborated-text)",
  HIGH_CONFIDENCE: "var(--confidence-high_confidence-text)",
  CONTRADICTED: "var(--confidence-contradicted-text)",
};

export const CONFIDENCE_LABEL_TR: Record<KnowledgeState, string> = {
  UNKNOWN: "Bilinmiyor",
  OBSERVED: "Gözlemlendi",
  REPORTED: "Bildirildi",
  SUPPORTED: "Destekleniyor",
  CORROBORATED: "Doğrulandı",
  HIGH_CONFIDENCE: "Yüksek Güven",
  CONTRADICTED: "Çelişkili",
};

export function ConfidenceBadge({
  state,
  confidence,
  className,
}: {
  state: KnowledgeState;
  confidence?: number;
  className?: string;
}) {
  const color = CONFIDENCE_COLOR_VAR[state];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium",
        className
      )}
      style={{ borderColor: color, color: CONFIDENCE_TEXT_VAR[state] }}
    >
      <span
        aria-hidden
        className="h-1.5 w-1.5 rounded-full"
        style={{ backgroundColor: color, boxShadow: `0 0 6px ${color}` }}
      />
      {CONFIDENCE_LABEL_TR[state]}
      {typeof confidence === "number" && (
        <span className="font-mono text-[10px] tabular-nums opacity-80">{Math.round(confidence * 100)}%</span>
      )}
    </span>
  );
}

/** İmza öğe: Confidence Spectrum'u gerçek, tıklanabilir bir lejant/filtre olarak gösterir. */
export function ConfidenceRail({
  active,
  onSelect,
}: {
  active?: KnowledgeState | null;
  onSelect?: (state: KnowledgeState | null) => void;
}) {
  return (
    <div className="flex flex-col gap-1" role="group" aria-label="Confidence Spectrum">
      {CONFIDENCE_ORDER.map((state) => {
        const isActive = active === state;
        return (
          <button
            key={state}
            type="button"
            // Bu butonlar bir filtre anahtarı; `aria-pressed` olmadan ekran okuyucu
            // "hangi durum seçili" sorusunu cevaplayamıyordu — görsel olarak sadece
            // arkaplan tonu değişiyor, o da duyurulmuyor.
            aria-pressed={isActive}
            onClick={() => onSelect?.(isActive ? null : state)}
            className={cn(
              "flex items-center gap-2 rounded-md px-2 py-1 text-left text-xs transition-colors",
              isActive ? "bg-surface-raised text-foreground" : "text-text-secondary hover:text-foreground"
            )}
          >
            <span
              aria-hidden
              className="h-2 w-4 rounded-sm"
              style={{ backgroundColor: CONFIDENCE_COLOR_VAR[state] }}
            />
            {CONFIDENCE_LABEL_TR[state]}
          </button>
        );
      })}
      <div className="my-1 h-px bg-border" />
      <button
        type="button"
        aria-pressed={active === "CONTRADICTED"}
        onClick={() => onSelect?.(active === "CONTRADICTED" ? null : "CONTRADICTED")}
        className={cn(
          "flex items-center gap-2 rounded-md px-2 py-1 text-left text-xs transition-colors",
          active === "CONTRADICTED" ? "bg-surface-raised text-foreground" : "text-text-secondary hover:text-foreground"
        )}
      >
        <span
          aria-hidden
          className="h-2 w-4 rounded-sm"
          style={{ backgroundColor: CONFIDENCE_COLOR_VAR.CONTRADICTED }}
        />
        {CONFIDENCE_LABEL_TR.CONTRADICTED}
      </button>
    </div>
  );
}
