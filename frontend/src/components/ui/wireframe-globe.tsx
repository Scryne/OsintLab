/**
 * Orijinal, lisanssız-risk taşımayan wireframe globe motifi — Scryne'ın paylaştığı
 * referans görsellerin (siyah zemin, ince beyaz çizgi wireframe/nokta-harita) dilini
 * OSINT/global-istihbarat temasına bağlıyor. Saf SVG, `currentColor` ile renklendirilir —
 * kullanan yer opacity/rengi kendi `text-*` class'ıyla kontrol eder (bkz. kullanım yerleri:
 * EmptyState, sidebar marka alanı, ana sayfa hero arkaplanı).
 */
export function WireframeGlobe({ className, spin }: { className?: string; spin?: boolean }) {
  return (
    <svg
      viewBox="0 0 200 200"
      fill="none"
      stroke="currentColor"
      strokeWidth={0.75}
      className={spin ? `${className ?? ""} animate-wireframe-spin` : className}
      aria-hidden
    >
      {/* Dış hat + merkez meridyen */}
      <circle cx="100" cy="100" r="90" />
      <line x1="100" y1="10" x2="100" y2="190" />
      {/* Meridyenler (dikey elipsler) */}
      <ellipse cx="100" cy="100" rx="64" ry="90" />
      <ellipse cx="100" cy="100" rx="31" ry="90" />
      {/* Paralel daireler (yatay elipsler) */}
      <ellipse cx="100" cy="100" rx="90" ry="18" />
      <ellipse cx="100" cy="65" rx="83" ry="14" />
      <ellipse cx="100" cy="135" rx="83" ry="14" />
      <ellipse cx="100" cy="35" rx="62" ry="10" />
      <ellipse cx="100" cy="165" rx="62" ry="10" />
    </svg>
  );
}
