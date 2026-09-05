"use client";

import { createContext, useCallback, useContext, useState } from "react";
import { AlertCircle, CheckCircle2, Info } from "lucide-react";
import { cn } from "@/lib/utils";

type ToastVariant = "default" | "success" | "error";
interface ToastItem {
  id: string;
  message: string;
  variant: ToastVariant;
}

const ToastContext = createContext<((message: string, variant?: ToastVariant) => void) | null>(null);

const VARIANT_ICON: Record<ToastVariant, typeof Info> = {
  default: Info,
  success: CheckCircle2,
  error: AlertCircle,
};
const VARIANT_COLOR: Record<ToastVariant, string> = {
  default: "text-text-secondary",
  success: "text-confidence-supported-text",
  error: "text-priority-critical-text",
};

/** Bağımsızlıksız, minimal bir toast sistemi (YAGNI — react-hot-toast gibi bir kütüphaneye
 * bu ölçekte gerek yok, bkz. use-api.ts'nin aynı gerekçeyle React Query'i reddetmesi). */
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const toast = useCallback((message: string, variant: ToastVariant = "default") => {
    const id = Math.random().toString(36).slice(2);
    setToasts((prev) => [...prev, { id, message, variant }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 3200);
  }, []);

  return (
    <ToastContext.Provider value={toast}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-[100] flex w-full max-w-sm flex-col gap-2">
        {toasts.map((t) => {
          const Icon = VARIANT_ICON[t.variant];
          return (
            <div
              key={t.id}
              role="status"
              className="glass-panel glass-ring pointer-events-auto flex items-center gap-2.5 rounded-lg px-3.5 py-3 text-sm text-foreground shadow-2xl animate-in fade-in slide-in-from-bottom-2"
            >
              <Icon aria-hidden className={cn("h-4 w-4 shrink-0", VARIANT_COLOR[t.variant])} />
              <span className="min-w-0">{t.message}</span>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}
