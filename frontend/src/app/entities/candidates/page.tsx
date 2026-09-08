"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ChevronDown, ChevronRight, Undo2 } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import type { ExtractedEntityCandidate } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { EmptyState, ErrorState } from "@/components/ui/state";
import { SkeletonRows } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { TypeCombo } from "@/components/forms/type-combo";
import { useToast } from "@/components/ui/toast";

const ENTITY_TYPE_SUGGESTIONS = [
  "Organization", "Person", "Company", "Location",
  "AI Model", "Product", "Domain", "Malware", "Tehdit Aktörü",
];

type Tab = "pending" | "dismissed";

/** Faz 20 — Entity Adayı Çıkarma (deterministik).
 *
 * Entity'ler bugüne kadar YALNIZCA elle yaratıldı: 5 tane. Oysa claim'ler düzinelerce
 * kurum/kişi/ürün adı içeriyor ve hiçbiri grafa girmiyordu. Faz 18 ve 19 yeni eksenler açtı
 * (olay, ilişki) ama ikisi de mevcut entity'ler üzerinde çalışıyor — girdi dar kaldıkça graf
 * da dar kalır.
 *
 * Liste bir ÖNERİdir. Sistem "bu metinde özel isim gibi duran bir öbek var" der; bunun bir
 * entity olup olmadığına ve türüne kullanıcı karar verir (Design Principle #7). Eleme
 * kalıcıdır ve geri alınabilir: elenen aday listeden kalkar ama silinmez, yoksa aynı gürültü
 * her taramadan sonra yeniden karşına çıkardı (Q17).
 */
export default function EntityCandidatesPage() {
  const toast = useToast();
  const [tab, setTab] = useState<Tab>("pending");
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  const { data: pending, error, loading, reload } = useApi(() => api.entities.extractedCandidates(), []);
  const { data: all, reload: reloadAll } = useApi(() => api.entities.extractedCandidates(true), []);

  const dismissed = useMemo(
    () => (all ?? []).filter((c) => c.status === "DISMISSED"),
    [all]
  );
  const promoted = useMemo(() => (all ?? []).filter((c) => c.status === "PROMOTED"), [all]);

  // `pending ?? []` her render'da yeni bir dizi üretir; aşağıdaki useMemo'nun bağımlılığı
  // olduğu için memo hiç tutmazdı (lint bunu yakalıyor).
  const shown = useMemo(() => pending ?? [], [pending]);
  // Görünür olmayan bir aday seçili SAYILMAZ — Faz 16 kuyruğunda alınan karar: liste
  // değiştiğinde ekranda olmayan bir şeyi elemek sürpriz olurdu.
  const visibleKeys = useMemo(() => new Set(shown.map((c) => c.key)), [shown]);
  const activeSelection = useMemo(() => selected.filter((k) => visibleKeys.has(k)), [selected, visibleKeys]);

  function reloadBoth() {
    reload();
    reloadAll();
  }

  async function dismissSelected() {
    if (activeSelection.length === 0) return;
    setBusy(true);
    try {
      const res = await api.entities.dismissCandidates(activeSelection);
      toast(`${res.dismissed} aday elendi — geri alınabilir`, "success");
      setSelected([]);
      reloadBoth();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Eleme başarısız", "error");
    } finally {
      setBusy(false);
    }
  }

  async function restore(key: string) {
    setBusy(true);
    try {
      await api.entities.restoreCandidates([key]);
      toast("Aday listeye geri alındı", "success");
      reloadBoth();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Geri alınamadı", "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <header>
        <h1 className="font-display text-[2rem] font-semibold tracking-tight text-balance text-foreground">
          Entity Adayları
        </h1>
        <p className="max-w-2xl text-sm leading-relaxed text-text-secondary">
          Claim metinlerinde özel isim gibi duran öbekler, kaç farklı kaynakta geçtiğine göre
          sıralanır. Bu bir öneri listesi: sistem &quot;burada bir ad var&quot; der, bunun bir entity
          olup olmadığına ve türüne sen karar verirsin. Elediğin aday bir daha önerilmez —
          ama silinmez, ikinci sekmeden geri alabilirsin.
        </p>
      </header>

      <div className="flex flex-wrap items-center gap-4 rounded-xl border border-border bg-surface px-4 py-3 text-sm">
        <span className="text-text-secondary">
          <strong className="tabular-nums text-foreground">{shown.length}</strong> bekleyen aday
        </span>
        <span className="text-text-secondary">
          <strong className="tabular-nums text-foreground">{promoted.length}</strong> entity&apos;ye çevrildi
        </span>
        <span className="text-text-secondary">
          <strong className="tabular-nums text-foreground">{dismissed.length}</strong> elendi
        </span>
      </div>

      <Tabs value={tab} onValueChange={(v) => v && setTab(v as Tab)}>
        <TabsList>
          <TabsTrigger value="pending">Bekleyenler{shown.length > 0 ? ` · ${shown.length}` : ""}</TabsTrigger>
          <TabsTrigger value="dismissed">
            Elenenler{dismissed.length > 0 ? ` · ${dismissed.length}` : ""}
          </TabsTrigger>
        </TabsList>
      </Tabs>

      {tab === "pending" && (
        <>
          {shown.length > 0 && (
            <div
              className={
                activeSelection.length
                  ? "glass-panel sticky top-3 z-20 flex flex-wrap items-center gap-3 rounded-xl px-4 py-3"
                  : "flex flex-wrap items-center gap-3 rounded-xl border border-border bg-surface px-4 py-3"
              }
            >
              <Checkbox
                checked={activeSelection.length === shown.length && shown.length > 0}
                indeterminate={activeSelection.length > 0 && activeSelection.length < shown.length}
                onCheckedChange={(on) => setSelected(on ? shown.map((c) => c.key) : [])}
                aria-label="Tüm adayları seç"
              />
              <span className="text-sm text-text-secondary">
                {activeSelection.length ? (
                  <>
                    <strong className="tabular-nums text-foreground">{activeSelection.length}</strong> aday seçili
                  </>
                ) : (
                  <>Gürültüyü toplu ele, kalanları tek tek entity&apos;ye çevir.</>
                )}
              </span>
              <div className="ml-auto">
                <Button size="sm" variant="outline" onClick={dismissSelected} disabled={busy || activeSelection.length === 0}>
                  Seçilenleri ele
                </Button>
              </div>
            </div>
          )}

          {loading && <SkeletonRows />}
          {error && <ErrorState message={error.message} onRetry={reload} />}
          {!loading && !error && shown.length === 0 && (
            <EmptyState
              title="Bekleyen aday yok"
              description="Liste eritilmiş. Yeni gözlemler promote edildikçe yeni adaylar burada belirir."
            />
          )}

          <div className="flex flex-col gap-2">
            {shown.map((candidate) => (
              <CandidateRow
                key={candidate.key}
                candidate={candidate}
                checked={selected.includes(candidate.key)}
                onToggle={(on) =>
                  setSelected((prev) =>
                    on ? [...new Set([...prev, candidate.key])] : prev.filter((k) => k !== candidate.key)
                  )
                }
                onPromoted={reloadBoth}
              />
            ))}
          </div>
        </>
      )}

      {tab === "dismissed" && (
        <>
          {dismissed.length === 0 ? (
            <EmptyState title="Elenen aday yok" description="Elediğin adaylar burada durur ve geri alınabilir." />
          ) : (
            <div className="flex flex-col gap-2">
              {dismissed.map((candidate) => (
                <div
                  key={candidate.key}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-surface p-3"
                >
                  <span className="text-sm text-text-secondary">{candidate.name}</span>
                  <Button size="sm" variant="ghost" onClick={() => restore(candidate.key)} disabled={busy}>
                    <Undo2 aria-hidden className="h-4 w-4" />
                    Geri al
                  </Button>
                </div>
              ))}
            </div>
          )}

          {promoted.length > 0 && (
            <section>
              <h2 className="mb-2 text-sm font-medium uppercase tracking-wide text-text-tertiary">
                Entity&apos;ye çevrilenler ({promoted.length})
              </h2>
              <div className="flex flex-wrap gap-1.5">
                {promoted.map((candidate) =>
                  candidate.promoted_entity_id ? (
                    <Link key={candidate.key} href={`/entities/${candidate.promoted_entity_id}`}>
                      <Badge variant="outline">{candidate.name}</Badge>
                    </Link>
                  ) : (
                    <Badge key={candidate.key} variant="outline">
                      {candidate.name}
                    </Badge>
                  )
                )}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}

function CandidateRow({
  candidate,
  checked,
  onToggle,
  onPromoted,
}: {
  candidate: ExtractedEntityCandidate;
  checked: boolean;
  onToggle: (on: boolean) => void;
  onPromoted: () => void;
}) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [showEvidence, setShowEvidence] = useState(false);
  const [name, setName] = useState(candidate.name);
  const [entityType, setEntityType] = useState("Organization");
  const [busy, setBusy] = useState(false);

  async function promote() {
    if (!name.trim() || !entityType.trim()) return;
    setBusy(true);
    try {
      await api.entities.promoteCandidates([
        { key: candidate.key, name: name.trim(), entity_type: entityType.trim() },
      ]);
      toast(`"${name.trim()}" entity olarak eklendi`, "success");
      setOpen(false);
      onPromoted();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Eklenemedi", "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border bg-surface p-3">
      <div className="flex flex-wrap items-center gap-3">
        {/* Erişilebilir isim adayın kendisi: 86 satırda hepsine "Adayı seç" demek, ekran
            okuyucuda hangi satırda olduğunu yok ederdi. */}
        <Checkbox checked={checked} onCheckedChange={onToggle} aria-label={`Adayı seç: ${candidate.name}`} />
        <span className="min-w-0 flex-1 text-sm font-medium text-pretty text-foreground">{candidate.name}</span>
        <Badge variant="outline">{candidate.source_count} kaynak</Badge>
        <Badge variant="outline">{candidate.claim_count} claim</Badge>
        <Button size="sm" variant="outline" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
          {open ? "Vazgeç" : "Entity yap"}
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-3 pl-7">
        <button
          type="button"
          onClick={() => setShowEvidence((v) => !v)}
          aria-expanded={showEvidence}
          className="flex items-center gap-1 text-[11px] font-medium text-text-secondary hover:text-foreground"
        >
          {showEvidence ? <ChevronDown aria-hidden className="h-3 w-3" /> : <ChevronRight aria-hidden className="h-3 w-3" />}
          Nerede geçiyor?
        </button>
        <span className="text-[11px] text-text-tertiary">{candidate.source_names.join(", ")}</span>
      </div>

      {showEvidence && (
        <ul className="flex flex-col gap-1 pl-7">
          {candidate.evidence.map((ev) => (
            <li key={ev.claim_id} className="text-xs leading-relaxed text-pretty text-text-tertiary">
              {ev.excerpt}
            </li>
          ))}
        </ul>
      )}

      {open && (
        <div className="flex flex-wrap items-end gap-2 border-t border-border pt-2 pl-7">
          <div className="flex min-w-0 flex-1 flex-col gap-1.5">
            {/* Ad düzeltilebilir: çıkarma bir sınır hatası yapmış olabilir. */}
            <Label htmlFor={`candidate-name-${candidate.key}`}>İsim</Label>
            <Input
              id={`candidate-name-${candidate.key}`}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor={`candidate-type-${candidate.key}`}>Tür</Label>
            <TypeCombo
              id={`candidate-type-${candidate.key}`}
              value={entityType}
              onChange={setEntityType}
              suggestions={ENTITY_TYPE_SUGGESTIONS}
              placeholder="ör. Company"
            />
          </div>
          <Button onClick={promote} disabled={busy || !name.trim() || !entityType.trim()}>
            {busy ? "Ekleniyor…" : "Ekle"}
          </Button>
        </div>
      )}
    </div>
  );
}
