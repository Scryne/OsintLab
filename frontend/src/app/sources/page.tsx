"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Plus, Search } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import type { Source } from "@/lib/types";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ErrorState, EmptyState } from "@/components/ui/state";
import { SkeletonList } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { LineageDialog } from "@/components/forms/lineage-dialog";
import { TypeCombo } from "@/components/forms/type-combo";
import { useToast } from "@/components/ui/toast";
import { LineageDetectDialog } from "@/components/forms/lineage-detect-dialog";

// Öneri listesi — kural DEĞİL (bkz. TypeCombo).
const SOURCE_TYPE_SUGGESTIONS = [
  "haber sitesi", "resmi açıklama", "sosyal medya", "blog", "akademik yayın", "kamu kaydı",
];

export default function SourcesPage() {
  const { data: sources, error, loading, reload } = useApi(() => api.sources.list(), []);
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    if (!sources) return [];
    const q = query.trim().toLowerCase();
    if (!q) return sources;
    return sources.filter((s) => s.name.toLowerCase().includes(q) || s.source_type.toLowerCase().includes(q));
  }, [sources, query]);

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="font-display text-[2rem] font-semibold tracking-tight text-balance text-foreground">Kaynaklar</h1>
          <p className="text-sm text-text-secondary">Claim ve event&apos;lerin atıflı olduğu bilgi kaynakları.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {/* F37: Faz 6'nın otomatik türetme tespiti arayüzden hiç tetiklenemiyordu. */}
          <LineageDetectDialog onDetected={reload} />
          <NewSourceDialog onCreated={reload} existingTypes={sources?.map((s2) => s2.source_type) ?? []} />
        </div>
      </div>

      <div className="relative">
        <Search aria-hidden className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-tertiary" />
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="İsim veya tür ara…"
          aria-label="Kaynak ara"
          className="pl-9"
        />
      </div>

      {loading && <SkeletonList />}
      {error && <ErrorState error={error} onRetry={reload} />}
      {!loading && !error && filtered.length === 0 && (
        <EmptyState
          title={query ? "Eşleşen kaynak bulunamadı" : "Henüz kaynak yok"}
          description={query ? undefined : "Sağ üstteki butonla ilk kaynağı ekle."}
        />
      )}

      {!loading && (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {filtered.map((source) => (
            <SourceCard key={source.id} source={source} allSources={sources ?? []} />
          ))}
        </div>
      )}
    </div>
  );
}

function SourceCard({ source, allSources }: { source: Source; allSources: Source[] }) {
  return (
    <div className="flex flex-col gap-1.5 rounded-lg border border-border bg-surface p-4">
      <div className="flex items-center justify-between gap-2">
        {/* Faz 13: kartlar artık detay sayfasına açılıyor — lineage zinciri, kaynağın
            claim'leri ve otomatik taraması orada. */}
        <Link
          href={`/sources/${source.id}`}
          className="min-w-0 truncate font-medium text-foreground underline decoration-transparent underline-offset-4 transition-colors hover:decoration-white/40"
        >
          {source.name}
        </Link>
        <Badge variant="secondary" className="shrink-0">{source.source_type}</Badge>
      </div>
      <p className="font-mono text-xs text-text-tertiary">
        <span className="tabular-nums">güvenilirlik %{Math.round(source.reliability * 100)}</span>
        {source.url && (
          <>
            {" · "}
            <a href={source.url} target="_blank" rel="noreferrer" className="text-text-secondary underline decoration-white/20 underline-offset-2 hover:text-foreground hover:decoration-white/50">
              {source.url}
            </a>
          </>
        )}
      </p>
      <LineageDialog source={source} allSources={allSources} />
    </div>
  );
}

export function NewSourceDialog({ onCreated, existingTypes = [] }: { onCreated: () => void; existingTypes?: string[] }) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [sourceType, setSourceType] = useState(SOURCE_TYPE_SUGGESTIONS[0]);
  const [url, setUrl] = useState("");
  const [reliability, setReliability] = useState("0.5");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (!name.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.sources.create({
        name: name.trim(),
        source_type: sourceType,
        url: url.trim() || null,
        reliability: Number(reliability),
      });
      toast(`"${name.trim()}" eklendi`, "success");
      setName("");
      setUrl("");
      setReliability("0.5");
      setOpen(false);
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bilinmeyen hata");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button size="sm">
            <Plus aria-hidden className="h-4 w-4" />
            Yeni Kaynak
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Yeni kaynak ekle</DialogTitle>
          <DialogDescription>Toplama yapılabilecek yeni bir kaynak tanımlar. Güvenilirlik değeri confidence hesabına doğrudan girer.</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="source-name">İsim</Label>
            <Input id="source-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="ör. Anadolu Ajansı" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="source-type">Tür</Label>
            <TypeCombo
              id="source-type"
              value={sourceType}
              onChange={setSourceType}
              suggestions={[...SOURCE_TYPE_SUGGESTIONS, ...existingTypes]}
              placeholder="ör. haber sitesi, resmi açıklama"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="source-url">URL (opsiyonel)</Label>
            <Input id="source-url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://…" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="source-reliability">Güvenilirlik (0–1)</Label>
            <Input
              id="source-reliability"
              type="number"
              min={0}
              max={1}
              step={0.05}
              value={reliability}
              onChange={(e) => setReliability(e.target.value)}
            />
          </div>
          {error && <p className="text-sm text-priority-critical-text">{error}</p>}
        </div>
        <DialogFooter>
          <Button onClick={submit} disabled={submitting || !name.trim()}>
            {submitting ? "Ekleniyor…" : "Ekle"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
