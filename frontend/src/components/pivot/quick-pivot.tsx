"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Crosshair, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { selectorHref, type SelectorDetect } from "@/lib/types-pivot";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";

/** Herhangi bir değeri yapıştır → türü tanınır → seçici sayfasına git (yoksa yaratılır). */
export function QuickPivot() {
  const router = useRouter();
  const toast = useToast();
  const [value, setValue] = useState("");
  const [det, setDet] = useState<SelectorDetect | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const v = value.trim();
    if (!v) {
      const t = setTimeout(() => setDet(null), 0);
      return () => clearTimeout(t);
    }
    let alive = true;
    const t = setTimeout(() => {
      api.selectors.detect(v).then((d) => alive && setDet(d)).catch(() => alive && setDet(null));
    }, 200);
    return () => {
      alive = false;
      clearTimeout(t);
    };
  }, [value]);

  async function go() {
    if (!det?.id) return;
    setBusy(true);
    try {
      if (!det.exists) await api.selectors.create(value.trim());
      router.push(selectorHref(det.id));
    } catch (err) {
      toast(err instanceof Error ? err.message : "Açılamadı", "error");
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-2 rounded-xl border border-border bg-surface p-3">
      <label htmlFor="quick-pivot" className="flex items-center gap-2 text-sm font-medium text-foreground">
        <Crosshair aria-hidden className="h-4 w-4 text-text-tertiary" />
        Pivotla
      </label>
      <div className="flex gap-2">
        <Input
          id="quick-pivot"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && go()}
          placeholder="alan adı, IP, URL, hash, CVE-…, T1059, AS13335, BTC/ETH adresi, 41.01, 28.97 — defang'li yazım da olur"
          className="font-mono text-xs"
          autoComplete="off"
          spellCheck={false}
        />
        <Button onClick={go} disabled={!det?.id || busy}>
          {busy ? <Loader2 aria-hidden className="h-4 w-4 animate-spin" /> : <ArrowRight aria-hidden className="h-4 w-4" />}
          {det?.exists === false ? "Ekle ve aç" : "Aç"}
        </Button>
      </div>
      <p className="min-h-4 text-xs text-text-tertiary" aria-live="polite">
        {value.trim() && det?.kind && (
          <>
            {det.label} olarak tanındı: <span className="font-mono text-text-secondary">{det.value}</span>
            {det.exists ? " · grafta var" : " · yeni"}
          </>
        )}
        {value.trim() && det && !det.kind && "Tür tanınamadı."}
      </p>
    </div>
  );
}

