"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** Geri dönüşü UI'da olmayan aksiyonlar için (entity relation kaldırma, SAME_AS confirm)
 * hafif bir "emin misin?" adımı — native `confirm()` yerine uygulamanın kendi diliyle,
 * modal açmadan. 3 saniye içinde onaylanmazsa otomatik geri döner. */
export function ConfirmButton({
  onConfirm,
  children,
  confirmLabel = "Emin misin?",
  className,
  size = "sm",
  variant = "outline",
  "aria-label": ariaLabel,
}: {
  onConfirm: () => void;
  children: React.ReactNode;
  confirmLabel?: string;
  className?: string;
  size?: "default" | "sm" | "xs" | "icon" | "icon-sm" | "icon-xs";
  variant?: "outline" | "ghost" | "secondary";
  "aria-label"?: string;
}) {
  const [armed, setArmed] = useState(false);

  useEffect(() => {
    if (!armed) return;
    const timer = setTimeout(() => setArmed(false), 3000);
    return () => clearTimeout(timer);
  }, [armed]);

  if (armed) {
    return (
      <div className="inline-flex items-center gap-1.5">
        <span className="text-xs text-text-tertiary">{confirmLabel}</span>
        <Button
          size={size}
          variant="destructive"
          onClick={() => {
            setArmed(false);
            onConfirm();
          }}
        >
          Evet
        </Button>
        <Button size={size} variant="ghost" onClick={() => setArmed(false)}>
          Vazgeç
        </Button>
      </div>
    );
  }

  return (
    <Button size={size} variant={variant} className={cn(className)} aria-label={ariaLabel} onClick={() => setArmed(true)}>
      {children}
    </Button>
  );
}
