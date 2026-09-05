"use client";

import { useState } from "react";
import Link from "next/link";
import { Plus, Zap } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import type { ObservationPromoteResult, QueueItem } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { SearchablePicker } from "@/components/forms/searchable-picker";
import { TypeCombo } from "@/components/forms/type-combo";
import { ConfidenceBadge } from "@/components/provenance/confidence";
import { ProvenanceBlock } from "@/components/provenance/provenance-label";
import { SingleSourceNote } from "@/components/provenance/single-source-note";
import { useToast } from "@/components/ui/toast";

const PROMOTION_THRESHOLD = 0.45;

/** Faz 16 — hızlı promote: tam form yerine kısa yol.
 *
 * Faz 10'un promote diyaloğunda sekiz alan var (kaynak, entity/event, destekleyici kanıt,
 * çelişen kanıt, doğruladığı claim'ler, çeliştiği claim'ler, supersede). Hepsi gerçek
 * ihtiyaçlardan doğdu ve hiçbiri kaldırılmıyor — ama kuyruktaki tipik karar bunların
 * ikisiyle veriliyor: bu hangi kaynaktan geldi, hangi entity hakkında. Kalan altısı 223
 * kayıtlık bir kuyrukta yolu fiilen kapatan şeydi.
 *
 * Sistem ikisini de ÖNERİR (kaynak: gözlemin adresi hangi Source'un adresiyle aynı host'ta;
 * entity: metinde adı geçen bilinen entity), kullanıcı onaylar veya değiştirir — Design
 * Principle #7 kararı insanda bırakıyor, öneri onu ucuzlatıyor. */
export function QuickPromoteDialog({ item, onPromoted }: { item: QueueItem; onPromoted: () => void }) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const { data: sources, reload: reloadSources } = useApi(() => (open ? api.sources.list() : Promise.resolve([])), [open]);
  const { data: entities } = useApi(() => (open ? api.entities.list() : Promise.resolve([])), [open]);

  const [sourceId, setSourceId] = useState<string | null>(item.suggested_source_id);
  const [entityId, setEntityId] = useState<string | null>(item.suggested_entity_id);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ObservationPromoteResult | null>(null);

  /** Diyalog kapanırken sıfırla — effect'le değil, kapanma olayında. Öneriler bu anda
   * yeniden okunuyor: kuyruk arada yeniden yüklendiyse (ör. yeni bir Source eklendi) bir
   * sonraki açılış güncel öneriyle geliyor. */
  function reset() {
    setSourceId(item.suggested_source_id);
    setEntityId(item.suggested_entity_id);
    setResult(null);
    setError(null);
  }

  const sourceItems = (sources ?? []).map((s) => ({ id: s.id, label: s.name, sublabel: s.source_type }));
  const entityItems = (entities ?? []).map((e) => ({ id: e.id, label: e.name, sublabel: e.entity_type }));

  async function submit() {
    if (!sourceId) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.observations.promote(item.id, {
        source_id: sourceId,
        about_entity_id: entityId,
        about_event_id: null,
      });
      setResult(res);
      // Eşik altı bir HATA değil (bkz. SingleSourceNote): tek kaynaklı bir iddianın normal
      // sonucu. Bildirim de öyle söylüyor — "başarısız" tonunda bir mesaj 42 kayıtta üst üste
      // okununca sistemin çalışmadığı izlenimini veriyordu.
      toast(
        res.claim.confidence >= PROMOTION_THRESHOLD
          ? "Claim'e yükseltildi"
          : "Claim üretildi (REPORTED) — tek kaynak, doğrulanmayı bekliyor",
        "success"
      );
      onPromoted();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Bilinmeyen hata");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) reset();
      }}
    >
      <DialogTrigger
        render={
          <Button size="sm" variant={item.suggested_source_id ? "default" : "outline"}>
            <Zap aria-hidden className="h-4 w-4" />
            Hızlı promote
          </Button>
        }
      />
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Hızlı promote</DialogTitle>
          <DialogDescription>Tek bir gözlemi claim&apos;e yükseltir. Kaynak ve entity önerilir; onaylamadan önce kontrol et.</DialogDescription>
        </DialogHeader>

        {result ? (
          <div className="flex max-h-[60vh] flex-col gap-4 overflow-y-auto pr-1">
            <div className="rounded-lg border border-border bg-surface p-3">
              <div className="flex items-start justify-between gap-3">
                <p className="text-sm text-foreground">{result.claim.text.split("\n")[0]}</p>
                <ConfidenceBadge
                  state={result.claim.knowledge_state}
                  confidence={result.claim.confidence}
                  className="shrink-0"
                />
              </div>
            </div>
            {result.claim.confidence < PROMOTION_THRESHOLD && <SingleSourceNote />}
            {result.why_matters.length > 0 && (
              <div className="flex flex-col gap-1.5">
                {result.why_matters.map((reason, i) => (
                  <ProvenanceBlock key={i} type="SYSTEM_INFERENCE">
                    {reason.text}
                  </ProvenanceBlock>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="flex max-h-[60vh] flex-col gap-4 overflow-y-auto pr-1">
            {/* Q22: claim metni olacak ham içerik güvenilmeyen veridir — kararı verirken
                görünmesi şart, ama sınır içinde ve talimat olarak değil. */}
            <div className="rounded-lg border border-border bg-black/20 p-3">
              <p className="mb-1 text-[11px] uppercase tracking-wide text-text-tertiary">
                Claim metni olacak
              </p>
              <p className="max-h-32 overflow-y-auto whitespace-pre-wrap text-sm text-text-secondary">
                {item.raw_content}
              </p>
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="quick-promote-kaynak">
                Kaynak
                {item.suggested_source_id === sourceId && sourceId && (
                  <span className="ml-1.5 text-xs font-normal text-text-tertiary">
                    · {item.host} adresinden önerildi
                  </span>
                )}
              </Label>
              <SearchablePicker
                id="quick-promote-kaynak"
                items={sourceItems}
                value={sourceId}
                onChange={setSourceId}
                placeholder="Kaynak ara…"
              />
              {!sourceId && item.host && (
                <CreateSourceInline
                  host={item.host}
                  onCreated={(id) => {
                    setSourceId(id);
                    reloadSources();
                  }}
                />
              )}
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="quick-promote-entity">
                İlgili entity
                {item.suggested_entity_id === entityId && entityId && (
                  <span className="ml-1.5 text-xs font-normal text-text-tertiary">
                    · metinde adı geçtiği için önerildi
                  </span>
                )}
              </Label>
              <SearchablePicker
                id="quick-promote-entity"
                items={entityItems}
                value={entityId}
                onChange={setEntityId}
                placeholder="Entity ara…"
              />
              {!entityId && (
                <p className="rounded-lg border border-priority-high/30 bg-priority-high/5 px-3 py-2 text-xs leading-relaxed text-text-secondary">
                  <span className="font-medium text-foreground">Bağlanmazsa bu claim yalıtık kalır.</span>{" "}
                  Memory Recall onu bulamaz, entity sayfasında ve Obsidian vault notunda görünmez.
                </p>
              )}
            </div>

            <p className="text-xs leading-relaxed text-text-tertiary">
              Kanıt bağı, çelişki, supersede ve event bağlantısı bu kısa yolda yok — onlar için{" "}
              <Link
                href="/observations"
                className="underline decoration-white/20 underline-offset-2 hover:text-foreground"
              >
                Gözlemler sayfasındaki tam form
              </Link>
              .
            </p>

            {error && <p className="text-sm text-priority-critical-text">{error}</p>}
          </div>
        )}

        <DialogFooter>
          {result ? (
            <Button onClick={() => setOpen(false)}>Kapat</Button>
          ) : (
            <Button onClick={submit} disabled={submitting || !sourceId}>
              {submitting ? "Yükseltiliyor…" : "Promote et"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Kuyrukta gerçekten karşılaşılan durum: 30 gözlem `cisa.gov`'dan geliyor ama o adres için
 * hiç Source kaydı yok — promote kaynaksız yapılamadığı için o 30 kayıt kısa yola kapalıydı.
 * Kaynağı kuyruktan çıkmadan kurabilmek, "gözlem başına bir sayfa gezinmesi" maliyetini
 * ortadan kaldırıyor. Güvenilirlik varsayılanı 0.5 (nötr) — uydurulmuş bir değer yerine
 * kullanıcının bilinçli olarak değiştireceği bir başlangıç. */
function CreateSourceInline({ host, onCreated }: { host: string; onCreated: (id: string) => void }) {
  const toast = useToast();
  const [openForm, setOpenForm] = useState(false);
  const [name, setName] = useState(host);
  const [sourceType, setSourceType] = useState("haber sitesi");
  const [reliability, setReliability] = useState("0.5");
  const [saving, setSaving] = useState(false);

  if (!openForm) {
    return (
      <Button size="sm" variant="ghost" className="self-start" onClick={() => setOpenForm(true)}>
        <Plus aria-hidden className="h-4 w-4" />
        {host} için kaynak yok — oluştur
      </Button>
    );
  }

  async function save() {
    const value = Number(reliability);
    if (!name.trim() || !Number.isFinite(value) || value < 0 || value > 1) return;
    setSaving(true);
    try {
      const source = await api.sources.create({
        name: name.trim(),
        source_type: sourceType.trim() || "haber sitesi",
        url: `https://${host}`,
        reliability: value,
      });
      toast(`Kaynak oluşturuldu: ${source.name}`, "success");
      onCreated(source.id);
    } catch (err) {
      toast(err instanceof Error ? err.message : "Kaynak oluşturulamadı", "error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border bg-surface p-3">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor={`src-name-${host}`}>Kaynak adı</Label>
        <Input id={`src-name-${host}`} value={name} onChange={(e) => setName(e.target.value)} />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor={`src-type-${host}`}>Tür</Label>
        <TypeCombo
          id={`src-type-${host}`}
          value={sourceType}
          onChange={setSourceType}
          suggestions={["haber sitesi", "resmi açıklama", "sosyal medya", "blog", "rapor"]}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor={`src-rel-${host}`}>Güvenilirlik (0–1)</Label>
        <Input
          id={`src-rel-${host}`}
          type="number"
          min={0}
          max={1}
          step={0.05}
          value={reliability}
          onChange={(e) => setReliability(e.target.value)}
        />
      </div>
      <div className="flex items-center gap-2">
        <Button size="sm" onClick={save} disabled={saving || !name.trim()}>
          {saving ? "Kaydediliyor…" : "Oluştur ve seç"}
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setOpenForm(false)}>
          Vazgeç
        </Button>
      </div>
    </div>
  );
}
