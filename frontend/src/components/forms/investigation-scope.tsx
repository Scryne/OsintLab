"use client";

import { useMemo, useState } from "react";
import { Plus, X } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { SearchablePicker } from "@/components/forms/searchable-picker";
import { EmptyState } from "@/components/ui/state";
import { useToast } from "@/components/ui/toast";

/**
 * Bir investigation'ın kapsamı: hangi entity/event'leri kapsıyor (Faz 11 tarama bulgusu F35).
 *
 * Bu bölüm hiç yoktu. Backend'de `PUT /investigations/{id}/entities/{id}` ve `.../events/{id}`
 * uçları vardı ama arayüz ikisini de hiç çağırmıyordu; okuma ucu (`GET .../scope`) ise hiç
 * yazılmamıştı — yani kapsam kurulsa bile geri okunamıyordu. Faz 3'ün "Research Question →
 * Scope → Entities → ..." akışının Scope adımı fiilen erişilemezdi.
 *
 * Kapsamdan çıkarma da eklendi: kapsam bir çalışma alanı tanımı, geçmiş kaydı değil —
 * yanlış eklenen düzeltilebilmeli (bkz. F16/F23b/F29, aynı ders üç kez tekrarlandı).
 */
export function InvestigationScope({ investigationId }: { investigationId: string }) {
  const toast = useToast();
  const { data: scope, reload } = useApi(() => api.investigations.scope(investigationId), [investigationId]);
  const [busy, setBusy] = useState<string | null>(null);

  async function remove(kind: "entity" | "event", id: string) {
    setBusy(id);
    try {
      if (kind === "entity") await api.investigations.removeEntity(investigationId, id);
      else await api.investigations.removeEvent(investigationId, id);
      toast("Kapsamdan çıkarıldı", "default");
      reload();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Çıkarılamadı", "error");
    } finally {
      setBusy(null);
    }
  }

  const entities = scope?.entities ?? [];
  const events = scope?.events ?? [];

  return (
    <section>
      <div className="mb-2 flex items-center justify-between gap-3">
        <h2 className="text-sm font-medium uppercase tracking-wide text-text-tertiary">Kapsam</h2>
        <div className="flex items-center gap-1.5">
          <ScopeAddDialog investigationId={investigationId} kind="entity" onAdded={reload} />
          <ScopeAddDialog investigationId={investigationId} kind="event" onAdded={reload} />
        </div>
      </div>
      {entities.length === 0 && events.length === 0 ? (
        <EmptyState
          title="Kapsam boş"
          description="Bu investigation'ın hangi entity ve event'leri incelediğini buradan tanımla."
        />
      ) : (
        <div className="flex flex-col gap-2">
          {entities.map((e) => (
            <div key={e.id} className="flex items-center justify-between gap-3 rounded-lg border border-border bg-surface p-3">
              <p className="min-w-0 text-sm text-foreground">
                {e.name} <span className="text-xs text-text-tertiary">· {e.entity_type}</span>
              </p>
              <Button
                size="sm"
                variant="ghost"
                aria-label={`${e.name} kaydını kapsamdan çıkar`}
                disabled={busy === e.id}
                onClick={() => remove("entity", e.id)}
              >
                <X aria-hidden className="h-4 w-4" />
              </Button>
            </div>
          ))}
          {events.map((ev) => (
            <div key={ev.id} className="flex items-center justify-between gap-3 rounded-lg border border-border bg-surface p-3">
              <p className="min-w-0 text-sm text-foreground">
                {ev.title} <span className="text-xs text-text-tertiary">· {ev.event_type}</span>
              </p>
              <Button
                size="sm"
                variant="ghost"
                aria-label={`${ev.title} event'ini kapsamdan çıkar`}
                disabled={busy === ev.id}
                onClick={() => remove("event", ev.id)}
              >
                <X aria-hidden className="h-4 w-4" />
              </Button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function ScopeAddDialog({
  investigationId,
  kind,
  onAdded,
}: {
  investigationId: string;
  kind: "entity" | "event";
  onAdded: () => void;
}) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const { data: entities } = useApi(() => api.entities.list(), [open, kind]);
  const { data: events } = useApi(() => api.events.list(), [open, kind]);
  const [pickedId, setPickedId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const items = useMemo(() => {
    if (kind === "entity") {
      return (entities ?? []).map((e) => ({ id: e.id, label: e.name, sublabel: e.entity_type }));
    }
    return (events ?? []).map((e) => ({ id: e.id, label: e.title, sublabel: e.event_type }));
  }, [entities, events, kind]);

  async function submit() {
    if (!pickedId) return;
    setSubmitting(true);
    try {
      if (kind === "entity") await api.investigations.addEntity(investigationId, pickedId);
      else await api.investigations.addEvent(investigationId, pickedId);
      toast("Kapsama eklendi", "success");
      setPickedId(null);
      setOpen(false);
      onAdded();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Eklenemedi", "error");
    } finally {
      setSubmitting(false);
    }
  }

  const etiket = kind === "entity" ? "Entity" : "Event";

  return (
    <Dialog open={open} onOpenChange={(next) => { setOpen(next); if (!next) setPickedId(null); }}>
      <DialogTrigger
        render={
          <Button size="sm" variant="outline">
            <Plus aria-hidden className="h-3.5 w-3.5" />
            {etiket} ekle
          </Button>
        }
      />
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Kapsama {etiket.toLowerCase()} ekle</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-1.5">
          <Label>{etiket}</Label>
          <SearchablePicker items={items} value={pickedId} onChange={setPickedId} placeholder={`${etiket} ara…`} />
        </div>
        <DialogFooter>
          <Button onClick={submit} disabled={submitting || !pickedId}>
            {submitting ? "Ekleniyor…" : "Ekle"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
