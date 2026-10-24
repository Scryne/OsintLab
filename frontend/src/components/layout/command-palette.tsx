"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Crosshair, CornerDownLeft, Loader2, Search } from "lucide-react";
import { api } from "@/lib/api";
import { selectorHref, type SearchResult } from "@/lib/types-pivot";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";

type Row = { key: string; href: string; title: string; subtitle?: string | null; group: string; action?: () => Promise<void> };

/** Faz 33 — komut paleti (Ctrl+K / ⌘K, ya da "/").
 *
 * Profesyonel bir araştırmada en sık yapılan şey bir değeri bir yerden kopyalayıp "bunu biliyor
 * muyum" diye sormak. Palet bunu her sayfadan tek tuşa indirir: yapıştırılan değer bir seçiciyse
 * türü tanınır ve ilk satır "Pivotla" olur; değilse entity, olay, investigation, kaynak, seçici ve
 * claim metinlerinde aranır. Klavye ile tamamen kullanılabilir (↑ ↓ Enter, Esc). */
export function CommandPalette() {
  const router = useRouter();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [result, setResult] = useState<SearchResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const target = e.target as HTMLElement | null;
      const typing = target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable);
      if ((e.key === "k" || e.key === "K") && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        setOpen((o) => !o);
      } else if (e.key === "/" && !typing && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        setOpen(true);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    const value = q.trim();
    if (!open || !value) {
      const t = setTimeout(() => setResult(null), 0);
      return () => clearTimeout(t);
    }
    let alive = true;
    const t = setTimeout(() => {
      setLoading(true);
      api
        .search(value)
        .then((r) => {
          if (alive) {
            setResult(r);
            setActive(0);
          }
        })
        .catch(() => alive && setResult(null))
        .finally(() => alive && setLoading(false));
    }, 180);
    return () => {
      alive = false;
      clearTimeout(t);
    };
  }, [q, open]);

  const rows: Row[] = useMemo(() => {
    const out: Row[] = [];
    const det = result?.detected;
    if (det) {
      out.push({
        key: `pivot:${det.id}`,
        href: selectorHref(det.id),
        title: det.value,
        subtitle: `${det.label} — ${det.exists ? "grafta var, aç" : "yeni seçici olarak ekle ve aç"}`,
        group: "Pivotla",
        action: det.exists
          ? undefined
          : async () => {
              await api.selectors.create(q.trim());
            },
      });
    }
    for (const g of result?.groups ?? []) {
      for (const item of g.items) {
        out.push({ key: `${g.key}:${item.id}`, href: item.href, title: item.title, subtitle: item.subtitle, group: g.label });
      }
    }
    return out;
  }, [result, q]);

  const go = useCallback(
    async (row: Row | undefined) => {
      if (!row) return;
      try {
        if (row.action) await row.action();
        setOpen(false);
        setQ("");
        router.push(row.href);
      } catch (err) {
        toast(err instanceof Error ? err.message : "Açılamadı", "error");
      }
    },
    [router, toast]
  );

  function onInputKey(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(rows.length - 1, a + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(0, a - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      go(rows[active]);
    }
  }

  let lastGroup = "";
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent showCloseButton={false} className="top-[15%] translate-y-0 gap-0 p-0 sm:max-w-xl" initialFocus={inputRef}>
        <DialogTitle className="sr-only">Ara ya da pivotla</DialogTitle>
        <div className="flex items-center gap-2 border-b border-border px-3">
          {loading ? <Loader2 aria-hidden className="h-4 w-4 animate-spin text-text-tertiary" /> : <Search aria-hidden className="h-4 w-4 text-text-tertiary" />}
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={onInputKey}
            placeholder="Ara ya da bir değer yapıştır: alan adı, IP, hash, CVE, kurum adı…"
            aria-label="Ara ya da pivotla"
            aria-controls="palette-results"
            aria-activedescendant={rows[active] ? `palette-${active}` : undefined}
            className="h-12 w-full bg-transparent text-sm text-foreground outline-none placeholder:text-text-tertiary"
            autoComplete="off"
            spellCheck={false}
          />
          <kbd className="rounded border border-border px-1.5 py-0.5 font-mono text-[10px] text-text-tertiary">Esc</kbd>
        </div>
        <ul id="palette-results" role="listbox" className="max-h-[55vh] overflow-y-auto p-1.5">
          {!q.trim() && (
            <li className="px-3 py-6 text-center text-xs text-text-tertiary">
              Ctrl+K ya da / ile her sayfadan açılır. Defang&apos;li değerler (hxxp, [.]) de tanınır.
            </li>
          )}
          {q.trim() && !loading && rows.length === 0 && result && (
            <li className="px-3 py-6 text-center text-xs text-text-tertiary">Sonuç yok — değer bir seçici olarak da tanınmadı.</li>
          )}
          {rows.map((row, i) => {
            const header = row.group !== lastGroup ? row.group : null;
            lastGroup = row.group;
            return (
              <li key={row.key} role="presentation">
                {header && <div className="px-2.5 pb-1 pt-2 text-[10px] font-medium uppercase tracking-wide text-text-tertiary">{header}</div>}
                <button
                  id={`palette-${i}`}
                  type="button"
                  role="option"
                  aria-selected={i === active}
                  onMouseMove={() => setActive(i)}
                  onClick={() => go(row)}
                  className={cn(
                    "flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left",
                    i === active ? "bg-white/[0.08]" : "hover:bg-white/[0.04]"
                  )}
                >
                  {row.group === "Pivotla" ? (
                    <Crosshair aria-hidden className="h-4 w-4 shrink-0 text-brand-accent-text" />
                  ) : (
                    <ArrowRight aria-hidden className="h-3.5 w-3.5 shrink-0 text-text-tertiary" />
                  )}
                  <span className="min-w-0 flex-1">
                    <span className={cn("block truncate text-sm text-foreground", (row.group === "Pivotla" || row.group === "Seçiciler") && "font-mono text-xs")}>
                      {row.title}
                    </span>
                    {row.subtitle && <span className="block truncate text-[11px] text-text-tertiary">{row.subtitle}</span>}
                  </span>
                  {i === active && <CornerDownLeft aria-hidden className="h-3.5 w-3.5 shrink-0 text-text-tertiary" />}
                </button>
              </li>
            );
          })}
        </ul>
      </DialogContent>
    </Dialog>
  );
}

/** Nav'daki görünür tetikleyici — kısayolu bilmeyen için. */
export function CommandPaletteHint() {
  return (
    <button
      type="button"
      onClick={() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", ctrlKey: true }))}
      className="mb-3 flex w-full items-center gap-2 rounded-md border border-border bg-white/[0.03] px-2.5 py-1.5 text-xs text-text-tertiary hover:border-white/20 hover:text-text-secondary"
    >
      <Search aria-hidden className="h-3.5 w-3.5" />
      Ara / pivotla
      <kbd className="ml-auto rounded border border-border px-1 font-mono text-[10px]">Ctrl K</kbd>
    </button>
  );
}
