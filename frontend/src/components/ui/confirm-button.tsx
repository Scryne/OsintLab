"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";

/** Geri dönüşü UI'da olmayan aksiyonlar için (entity relation kaldırma, SAME_AS confirm)
 * hafif bir "emin misin?" adımı — native `confirm()` yerine uygulamanın kendi diliyle,
 * modal açmadan.
 *
 * 2026-09-06 erişilebilirlik onarımı, üç değişiklik:
 * 1. **3 saniyelik otomatik geri alma kaldırıldı** (WCAG 2.2.1 Timing Adjustable). Yıkıcı
 *    bir onayı 3 saniyeye sığdırmak, yavaş okuyan veya motor güçlüğü olan bir kullanıcı
 *    için kararı fiilen imkânsız kılıyordu. Yerine Escape ve dışarı tıklama geldi —
 *    ikisi de kullanıcının kendi hızında.
 * 2. **Odak korunuyor.** Armed olunca tetikleyici buton DOM'dan kalkıyor ve odak `body`'ye
 *    düşüyordu; klavye kullanıcısı sayfanın başına dönüyordu. Artık odak onay butonuna
 *    taşınıyor, vazgeçilince tetikleyiciye geri dönüyor.
 * 3. **Değişim duyuruluyor.** Butonun üç butona dönüşmesi ekran okuyucuya hiç
 *    bildirilmiyordu; `role="alert"` bunu sesli kılıyor.
 *
 * `confirmAction` metni zorunlu değil ama önerilir: onay düğmesi eylemi tekrar etmeli
 * ("Bağlantıyı kaldır"), "Evet" demek neyin onaylandığını söylemiyor.
 *
 * `onConfirm` async olabilir; başarısız olursa hata burada toast olarak gösterilir.
 * 2026-10-18'e kadar çağıranların çoğu (olaydan claim/entity çıkarma) hatayı yakalamıyordu:
 * istek reddedildiğinde hiçbir şey olmuyor gibi görünüyordu. */
export function ConfirmButton({
  onConfirm,
  children,
  confirmLabel = "Emin misin?",
  confirmAction = "Evet",
  className,
  size = "sm",
  variant = "outline",
  "aria-label": ariaLabel,
}: {
  onConfirm: () => void | Promise<void>;
  children: React.ReactNode;
  confirmLabel?: string;
  /** Onay düğmesinin metni — eylemi tekrar etmeli. */
  confirmAction?: string;
  className?: string;
  size?: "default" | "sm" | "xs" | "icon" | "icon-sm" | "icon-xs";
  variant?: "outline" | "ghost" | "secondary";
  "aria-label"?: string;
}) {
  const toast = useToast();
  const [armed, setArmed] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  // Vazgeçildiğinde odağı tetikleyiciye geri vermek için: tetikleyici o anda henüz
  // render edilmemiş olduğundan bayrakla bir sonraki render'a bırakılıyor.
  const restoreFocus = useRef(false);

  useEffect(() => {
    if (armed) {
      confirmRef.current?.focus();
      return;
    }
    if (restoreFocus.current) {
      restoreFocus.current = false;
      triggerRef.current?.focus();
    }
  }, [armed]);

  function disarm(restore = true) {
    restoreFocus.current = restore;
    setArmed(false);
  }

  useEffect(() => {
    if (!armed) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") disarm();
    }
    function onPointer(e: PointerEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) disarm(false);
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer);
    };
  }, [armed]);

  if (armed) {
    return (
      <div ref={wrapRef} role="alert" className="inline-flex items-center gap-1.5">
        <span className="text-xs text-text-tertiary">{confirmLabel}</span>
        <Button
          ref={confirmRef}
          size={size}
          variant="destructive"
          onClick={() => {
            restoreFocus.current = false;
            setArmed(false);
            Promise.resolve()
              .then(onConfirm)
              .catch((err) => toast(err instanceof Error ? err.message : "İşlem başarısız", "error"));
          }}
        >
          {confirmAction}
        </Button>
        <Button size={size} variant="ghost" onClick={() => disarm()}>
          Vazgeç
        </Button>
      </div>
    );
  }

  return (
    <Button
      ref={triggerRef}
      size={size}
      variant={variant}
      className={cn(className)}
      aria-label={ariaLabel}
      onClick={() => setArmed(true)}
    >
      {children}
    </Button>
  );
}
