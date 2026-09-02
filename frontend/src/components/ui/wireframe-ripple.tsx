/**
 * Orijinal wireframe "ripple/radar" motifi — WireframeGlobe ile aynı dil. Sinyal/dalga/derinleşen
 * araştırma hissi taşıyor, Investigation'lar sayfasında kullanılıyor.
 */
export function WireframeRipple({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 200 200" fill="none" stroke="currentColor" strokeWidth={0.75} className={className} aria-hidden>
      <circle cx="140" cy="90" r="18" />
      <circle cx="140" cy="90" r="38" />
      <circle cx="140" cy="90" r="58" />
      <circle cx="140" cy="90" r="78" />
      <circle cx="140" cy="90" r="98" />
      <line x1="140" y1="72" x2="140" y2="108" strokeWidth={1.25} />
      <line x1="122" y1="90" x2="158" y2="90" strokeWidth={1.25} />
    </svg>
  );
}
