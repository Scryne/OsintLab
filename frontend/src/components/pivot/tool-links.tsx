"use client";

import { useMemo, useState } from "react";
import { Check, Copy, ExternalLink, Lock, Search } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import type { ToolLink } from "@/lib/types-pivot";
import { SkeletonRows } from "@/components/ui/skeleton";
import { ErrorState, EmptyState } from "@/components/ui/state";

const COST: Record<ToolLink["cost"], string> = { free: "ücretsiz", freemium: "kısmen ücretsiz", paid: "ücretli" };

/** Faz 32 — dış araç bağlantıları. Backend bu araçlara istek atmaz; bağlantı kullanıcının
 * tarayıcısında açılır. Bu yüzden OPSEC notu burada: giriş yapılmış bir hesapla açılan
 * bağlantı, aramayı o hesaba bağlar. */
export function ToolLinks({ kind, value }: { kind: string; value: string }) {
  const { data, error, loading, reload } = useApi(() => api.tools.links(kind, value), [kind, value]);
  const groups = useMemo(() => {
    const out = new Map<string, ToolLink[]>();
    for (const link of data ?? []) {
      const list = out.get(link.category_label) ?? [];
      list.push(link);
      out.set(link.category_label, list);
    }
    return [...out.entries()];
  }, [data]);

  if (loading) return <SkeletonRows count={3} />;
  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (!groups.length) return <EmptyState title="Bu tür için hazır bağlantı yok" description="Araç Rehberi'nden elle arayabilirsin." />;

  return (
    <div className="flex flex-col gap-4">
      <p className="text-xs text-pretty text-text-tertiary">
        Bağlantılar tarayıcında açılır — OsintLab bu servislere istek atmaz. Hesabına giriş yapılmış bir tarayıcıda
        aramak, aramayı o hesapla ilişkilendirir.
      </p>
      {groups.map(([label, links]) => (
        <section key={label} className="flex flex-col gap-1.5">
          <h4 className="text-[11px] font-medium uppercase tracking-wide text-text-tertiary">{label}</h4>
          <ul className="grid gap-1.5 sm:grid-cols-2">
            {links.map((l) => (
              <li key={l.tool_id}>
                <a
                  href={l.url}
                  target="_blank"
                  rel="noopener noreferrer nofollow"
                  className="group flex h-full items-start justify-between gap-2 rounded-md border border-border bg-surface px-2.5 py-2 transition-colors hover:border-white/25 hover:bg-white/[0.07]"
                >
                  <span className="min-w-0">
                    <span className="flex items-center gap-1.5 text-sm text-foreground">
                      {l.name}
                      {l.account && <Lock aria-label="hesap gerekir" className="h-3 w-3 text-text-tertiary" />}
                    </span>
                    <span className="block text-[11px] text-text-tertiary">
                      {COST[l.cost]}
                      {l.note ? ` · ${l.note}` : ""}
                    </span>
                  </span>
                  <ExternalLink aria-hidden className="mt-0.5 h-3.5 w-3.5 shrink-0 text-text-tertiary group-hover:text-foreground" />
                </a>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

export function DorkList({ kind, value }: { kind: string; value: string }) {
  const { data, error, loading, reload } = useApi(() => api.tools.dorks(kind, value), [kind, value]);
  const [copied, setCopied] = useState<string | null>(null);

  async function copy(q: string) {
    try {
      await navigator.clipboard.writeText(q);
      setCopied(q);
      setTimeout(() => setCopied((c) => (c === q ? null : c)), 1500);
    } catch {
      // Pano izni yoksa sorgu zaten ekranda seçilebilir duruyor.
    }
  }

  if (loading) return <SkeletonRows count={2} />;
  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (!data?.length) return null;
  return (
    <ul className="flex flex-col gap-2">
      {data.map((d) => (
        <li key={d.query} className="rounded-md border border-border bg-surface p-2.5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="flex items-center gap-1.5 text-sm text-foreground">
              <Search aria-hidden className="h-3.5 w-3.5 text-text-tertiary" />
              {d.label}
            </span>
            <span className="flex flex-wrap gap-1">
              {d.engines.map((e) => (
                <a
                  key={e.id}
                  href={e.url}
                  target="_blank"
                  rel="noopener noreferrer nofollow"
                  className="rounded border border-border px-1.5 py-0.5 text-[11px] text-text-secondary hover:border-white/25 hover:text-foreground"
                >
                  {e.name}
                </a>
              ))}
            </span>
          </div>
          <div className="mt-1.5 flex items-start gap-2">
            <code className="min-w-0 flex-1 break-all font-mono text-[11px] text-text-secondary">{d.query}</code>
            <button
              type="button"
              onClick={() => copy(d.query)}
              aria-label="Sorguyu kopyala"
              className="shrink-0 rounded p-1 text-text-tertiary hover:bg-white/5 hover:text-foreground"
            >
              {copied === d.query ? <Check aria-hidden className="h-3.5 w-3.5" /> : <Copy aria-hidden className="h-3.5 w-3.5" />}
            </button>
          </div>
        </li>
      ))}
    </ul>
  );
}
