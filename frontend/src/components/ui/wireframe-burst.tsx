/**
 * Orijinal wireframe "burst/yıldız" motifi — WireframeGlobe ile aynı dil (ince çizgi,
 * currentColor), bir merkezden yayılan bağlantılar/ilişkiler hissi taşıyor. Entity'ler
 * (bir kişi/kurumdan yayılan ilişkiler) ve Olası Eşleşmeler (bir eşleşme etrafında toplanan
 * adaylar) sayfalarında kullanılıyor — globe her yerde tekrarlanmasın diye.
 */
export function WireframeBurst({ className, spin }: { className?: string; spin?: boolean }) {
  return (
    <svg
      viewBox="0 0 200 200"
      fill="none"
      stroke="currentColor"
      strokeWidth={0.75}
      className={spin ? `${className ?? ""} animate-wireframe-spin` : className}
      aria-hidden
    >
      {/* 8 sivri uç, merkezden yayılan */}
      <path d="M140.75,89.84 L195,100 L140.75,110.16" />
      <path d="M136.0,121.6 L167.2,167.2 L121.6,136.0" />
      <path d="M110.2,140.75 L100,195 L89.84,140.75" />
      <path d="M78.4,136.0 L32.8,167.2 L64.0,121.6" />
      <path d="M59.25,110.16 L5,100 L59.25,89.84" />
      <path d="M64.0,78.4 L32.8,32.8 L78.4,64.0" />
      <path d="M89.84,59.25 L100,5 L110.16,59.25" />
      <path d="M121.6,64.0 L167.2,32.8 L136.0,78.4" />
      {/* Merkez çekirdek — hacim hissi için iç içe daireler */}
      <circle cx="100" cy="100" r="42" />
      <circle cx="100" cy="100" r="26" />
      <ellipse cx="100" cy="100" rx="42" ry="14" />
      <ellipse cx="100" cy="100" rx="14" ry="42" />
    </svg>
  );
}
