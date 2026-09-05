import { Info } from "lucide-react";

/** Faz 16 ölçümü (2026-09-05): kuyruk eritilince promote edilen 43 claim'in **42'si** eşiğin
 * altında kaldı. Bu bir arıza değil, formülün matematiği — ve arayüz onu bir kayıp gibi
 * anlatıyordu.
 *
 * `confidence.py`: tek kaynaklı, doğrulanmamış, kanıtsız bir claim'in confidence'ı
 * `SOURCE_QUALITY_WEIGHT (0.40) × kaynak_güvenilirliği`. TechCrunch (0.70) → 0.28, OpenAI
 * resmi duyuru (0.75) → 0.30. **Mükemmel bir kaynak bile (1.0) yalnızca 0.40 verir**, yani
 * SUPPORTED eşiği (0.45) tek kaynakla YAPISAL OLARAK erişilemez. Bu bilinçli bir epistemik
 * karar: tek bir kaynak, tek başına "desteklenmiş" değildir.
 *
 * Eski metin ("Eşik (%45) geçilmedi") 42 kayıtta üst üste okununca sistemin çalışmadığı
 * izlenimi veriyordu. Doğru mesaj iki parçalı: bu beklenen sonuç, ve onu ne yükseltir. */
export function SingleSourceNote({ className }: { className?: string }) {
  return (
    <div
      className={`flex items-start gap-2 rounded-lg border border-border bg-surface px-3 py-2.5 text-xs leading-relaxed text-text-secondary ${className ?? ""}`}
    >
      <Info aria-hidden className="mt-0.5 h-3.5 w-3.5 shrink-0 text-text-tertiary" />
      <span>
        <span className="font-medium text-foreground">
          Tek kaynaklı bir iddia REPORTED olarak girer — beklenen sonuç, bir eksiklik değil.
        </span>{" "}
        Confidence&apos;ın %40&apos;ı kaynak güvenilirliğinden gelir; kalan %60 tek kaynakla
        açılamaz. Yükselmesi için{" "}
        <span className="text-foreground">ikinci, bağımsız bir kaynağın</span> aynı iddiayı
        doğrulaması (+%25 bağımsızlık, +%15 doğrulama) ya da bir{" "}
        <span className="text-foreground">kanıt dosyası</span> bağlanması (+%20) gerekiyor.
        Claim graf&apos;ta duruyor: Memory Recall onu buluyor, entity sayfasında ve Obsidian
        notunda görünüyor.
      </span>
    </div>
  );
}
