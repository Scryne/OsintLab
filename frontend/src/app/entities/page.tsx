"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Plus, Search } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import type { Entity } from "@/lib/types";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ErrorState, EmptyState } from "@/components/ui/state";
import { SkeletonList } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { TypeCombo } from "@/components/forms/type-combo";
import { useToast } from "@/components/ui/toast";
import { WireframeBurst } from "@/components/ui/wireframe-burst";

// Öneri listesi — kural DEĞİL (bkz. TypeCombo). Backend entity_type'ı serbest bırakır.
const ENTITY_TYPE_SUGGESTIONS = [
  "Person", "Organization", "Company", "Location",
  "AI Model", "Product", "Domain", "Vessel", "Aircraft", "Malware",
];

export default function EntitiesPage() {
  const { data: entities, error, loading, reload } = useApi(() => api.entities.list(), []);
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    if (!entities) return [];
    const q = query.trim().toLowerCase();
    if (!q) return entities;
    return entities.filter(
      (e) => e.name.toLowerCase().includes(q) || e.aliases.some((a) => a.toLowerCase().includes(q))
    );
  }, [entities, query]);

  return (
    <div className="relative isolate mx-auto flex max-w-4xl flex-col gap-6 overflow-hidden">
      <WireframeBurst spin className="pointer-events-none absolute -right-10 top-12 -z-10 h-48 w-48 text-white/5" />
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="font-display text-[2rem] font-semibold tracking-tight text-foreground">Entity&apos;ler</h1>
          <p className="text-sm text-text-secondary">Bilinen kişi, kurum ve lokasyonlar.</p>
        </div>
        <NewEntityDialog onCreated={reload} existingTypes={entities?.map((e) => e.entity_type) ?? []} />
      </div>

      <div className="relative">
        <Search aria-hidden className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-tertiary" />
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="İsim veya alias ara…"
          className="pl-9"
        />
      </div>

      {loading && <SkeletonList />}
      {error && <ErrorState message={error.message} onRetry={reload} />}
      {!loading && !error && filtered.length === 0 && (
        <EmptyState
          title={query ? "Eşleşen entity bulunamadı" : "Henüz entity yok"}
          description={query ? undefined : "Sağ üstteki butonla ilk entity'ni ekle."}
        />
      )}

      {!loading && (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {filtered.map((entity) => (
            <EntityCard key={entity.id} entity={entity} />
          ))}
        </div>
      )}
    </div>
  );
}

function EntityCard({ entity }: { entity: Entity }) {
  return (
    <Link
      href={`/entities/${entity.id}`}
      className="flex flex-col gap-1.5 rounded-lg border border-border bg-surface p-4 transition-colors hover:bg-surface-raised"
    >
      <div className="flex items-center justify-between">
        <span className="font-medium text-foreground">{entity.name}</span>
        <Badge variant="secondary">{entity.entity_type}</Badge>
      </div>
      {entity.aliases.length > 0 && (
        <p className="text-xs text-text-tertiary">Alias: {entity.aliases.join(", ")}</p>
      )}
    </Link>
  );
}

function NewEntityDialog({ onCreated, existingTypes }: { onCreated: () => void; existingTypes: string[] }) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [entityType, setEntityType] = useState(ENTITY_TYPE_SUGGESTIONS[0]);
  // Faz 11 (F30): `aliases` API'de baştan beri vardı ama formda alan yoktu — pratikte hep
  // boş kalıyordu, dolayısıyla SAME_AS tespitinin alias yarısı hiç çalışmamıştı.
  const [aliases, setAliases] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (!name.trim() || !entityType.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.entities.create({
        entity_type: entityType.trim(),
        name: name.trim(),
        aliases: aliases.split(",").map((a) => a.trim()).filter(Boolean),
      });
      toast(`"${name.trim()}" eklendi`, "success");
      setName("");
      setAliases("");
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
            Yeni Entity
          </Button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Yeni entity ekle</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="entity-name">İsim</Label>
            <Input id="entity-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="ör. Ahmet Yılmaz" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="entity-type">Tür</Label>
            <TypeCombo
              id="entity-type"
              value={entityType}
              onChange={setEntityType}
              suggestions={[...ENTITY_TYPE_SUGGESTIONS, ...existingTypes]}
              placeholder="ör. Organization, AI Model"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="entity-aliases">Alias&apos;lar (opsiyonel, virgülle ayır)</Label>
            <Input
              id="entity-aliases"
              value={aliases}
              onChange={(e) => setAliases(e.target.value)}
              placeholder="ör. INFINITE NIGHTMARE, MSNightmare"
            />
            <p className="text-xs text-text-tertiary">
              Aynı kaydın bilinen diğer isimleri — olası eşleşme tespitine girdi olur.
            </p>
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
