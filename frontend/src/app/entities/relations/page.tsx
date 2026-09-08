"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ArrowRight, Check, ChevronDown, ChevronRight, X } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import type { RelationPairCandidate } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { EmptyState, ErrorState } from "@/components/ui/state";
import { SkeletonRows } from "@/components/ui/skeleton";
import { TypeCombo } from "@/components/forms/type-combo";
import { useToast } from "@/components/ui/toast";

const RELATION_TYPE_SUGGESTIONS = [
  "ilişkili", "geliştirdi", "sahibi", "ortağı", "rakibi", "parçası",
  "hedef aldı", "dava açtı", "yatırım yaptı", "satın aldı", "çalışıyor", "bulunduğu yer",
];

const pairKey = (a: string, b: string) => `${a}::${b}`;

/** Faz 22 — ilişki adaylarının eritilmesi.
 *
 * Ölçüm (2026-09-08): graf'ta 1 kenar vardı, karşısında 109 açık aday çifti. Faz 19
 * mekanizmayı kurmuştu ve sınavını tek kenarla geçmişti. İki sebep ölçüldü: (a) 109 çift
 * için tek tek tür yazmak pahalı — üstelik "bu ikisi ilgisiz" demenin YOLU YOKTU, yani liste
 * hiç erimiyordu; (b) kurulan kenarın karşılığı hiçbir yerde graf olarak görünmüyordu.
 *
 * Bu ekran (a)'yı çözüyor: toplu reddetme ve toplu kurma. Tür hâlâ kullanıcıdan geliyor
 * (Design Principle #7) — ama artık bir kez yazılıp seçili çiftlerin tamamına uygulanabiliyor.
 */
export default function RelationCandidatesPage() {
  const toast = useToast();
  const { data, error, loading, reload } = useApi(() => api.entities.relationPairCandidates(), []);
  const [selected, setSelected] = useState<string[]>([]);
  const [bulkType, setBulkType] = useState("ilişkili");
  const [busy, setBusy] = useState(false);

  const candidates = useMemo(() => data ?? [], [data]);
  const allKeys = useMemo(
    () => candidates.map((c) => pairKey(c.a.entity_id, c.b.entity_id)),
    [candidates]
  );
  const visible = useMemo(() => new Set(allKeys), [allKeys]);
  const activeSelection = useMemo(() => selected.filter((k) => visible.has(k)), [selected, visible]);

  const byKey = useMemo(() => {
    const map = new Map<string, RelationPairCandidate>();
    for (const c of candidates) map.set(pairKey(c.a.entity_id, c.b.entity_id), c);
    return map;
  }, [candidates]);

  async function decide(keys: string[], action: "CREATE" | "REJECT", relationType = "") {
    if (keys.length === 0) return;
    if (action === "CREATE" && !relationType.trim()) {
      toast("Önce ilişkinin türünü yaz — sistem tahmin etmez", "error");
      return;
    }
    const decisions = keys
      .map((k) => byKey.get(k))
      .filter((c): c is RelationPairCandidate => Boolean(c))
      .map((c) => ({
        from_entity_id: c.a.entity_id,
        to_entity_id: c.b.entity_id,
        action,
        relation_type: relationType.trim(),
      }));
    setBusy(true);
    try {
      const res = await api.entities.decideRelations(decisions);
      toast(
        action === "CREATE" ? `${res.created} ilişki kuruldu` : `${res.rejected} çift ilgisiz işaretlendi`,
        "success"
      );
      setSelected([]);
      reload();
    } catch (err) {
      toast(err instanceof Error ? err.message : "İşlem başarısız", "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <header>
        <h1 className="font-display text-[2rem] font-semibold tracking-tight text-balance text-foreground">
          İlişki Adayları
        </h1>
        <p className="max-w-2xl text-sm leading-relaxed text-text-secondary">
          Aynı claim&apos;e bağlı ya da aynı olaya karışan entity çiftleri. Sistem yalnızca
          &quot;bu ikisi birbiriyle ilgili olabilir&quot; der; ilişkinin ne olduğunu sen yazarsın.
          İlgisiz bulduğun çifti reddet — bir daha önerilmez ama kaybolmaz.{" "}
          <Link href="/graph" className="underline decoration-white/20 underline-offset-2 hover:text-foreground hover:decoration-white/50">
            Kurulan ilişkileri graf&apos;ta gör →
          </Link>
        </p>
      </header>

      {candidates.length > 0 && (
        <div
          className={
            activeSelection.length
              ? "glass-panel sticky top-3 z-20 flex flex-col gap-3 rounded-xl px-4 py-3"
              : "flex flex-col gap-3 rounded-xl border border-border bg-surface px-4 py-3"
          }
        >
          <div className="flex flex-wrap items-center gap-3">
            <Checkbox
              checked={activeSelection.length === candidates.length && candidates.length > 0}
              indeterminate={activeSelection.length > 0 && activeSelection.length < candidates.length}
              onCheckedChange={(on) => setSelected(on ? allKeys : [])}
              aria-label="Tüm aday çiftleri seç"
            />
            <span className="text-sm text-text-secondary">
              {activeSelection.length ? (
                <>
                  <strong className="tabular-nums text-foreground">{activeSelection.length}</strong> çift seçili
                </>
              ) : (
                <>
                  <span className="tabular-nums text-foreground">{candidates.length}</span> aday çift
                </>
              )}
            </span>
            <div className="ml-auto">
              <Button
                size="sm"
                variant="outline"
                onClick={() => decide(activeSelection, "REJECT")}
                disabled={busy || activeSelection.length === 0}
              >
                <X aria-hidden className="h-4 w-4" />
                İlgisiz işaretle
              </Button>
            </div>
          </div>
          {/* Toplu kurma bilerek TEK bir tür alıyor: farklı türdeki çiftler tek hamlede
              bağlanmamalı, yoksa "ilişkili" gibi anlamsız bir tür her yere yayılır. */}
          <div className="flex flex-wrap items-end gap-2">
            <div className="flex min-w-0 flex-1 flex-col gap-1.5">
              <Label htmlFor="bulk-relation-type">Seçilenleri şu türle bağla</Label>
              <TypeCombo
                id="bulk-relation-type"
                value={bulkType}
                onChange={setBulkType}
                suggestions={RELATION_TYPE_SUGGESTIONS}
                placeholder="ör. geliştirdi"
              />
            </div>
            <Button
              size="sm"
              onClick={() => decide(activeSelection, "CREATE", bulkType)}
              disabled={busy || activeSelection.length === 0 || !bulkType.trim()}
            >
              <Check aria-hidden className="h-4 w-4" />
              Bağla ({activeSelection.length})
            </Button>
          </div>
        </div>
      )}

      {loading && <SkeletonRows />}
      {error && <ErrorState message={error.message} onRetry={reload} />}
      {!loading && !error && candidates.length === 0 && (
        <EmptyState
          title="Bekleyen ilişki adayı yok"
          description="Liste eritilmiş. Yeni claim bağları ya da olaylar eklendikçe yeni çiftler burada belirir."
          action={
            <Link href="/graph" className="text-sm text-text-secondary underline decoration-white/20 underline-offset-2 hover:text-foreground hover:decoration-white/50">
              Graf görünümüne git →
            </Link>
          }
        />
      )}

      <div className="flex flex-col gap-2">
        {candidates.map((candidate) => {
          const key = pairKey(candidate.a.entity_id, candidate.b.entity_id);
          return (
            <PairRow
              key={key}
              candidate={candidate}
              checked={selected.includes(key)}
              onToggle={(on) =>
                setSelected((prev) => (on ? [...new Set([...prev, key])] : prev.filter((k) => k !== key)))
              }
              onDecide={(action, type) => decide([key], action, type)}
              busy={busy}
            />
          );
        })}
      </div>
    </div>
  );
}

function PairRow({
  candidate,
  checked,
  onToggle,
  onDecide,
  busy,
}: {
  candidate: RelationPairCandidate;
  checked: boolean;
  onToggle: (on: boolean) => void;
  onDecide: (action: "CREATE" | "REJECT", relationType?: string) => void;
  busy: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [showEvidence, setShowEvidence] = useState(false);
  const [relationType, setRelationType] = useState("");
  const pairLabel = `${candidate.a.name} – ${candidate.b.name}`;

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border bg-surface p-3">
      <div className="flex flex-wrap items-center gap-3">
        <Checkbox checked={checked} onCheckedChange={onToggle} aria-label={`Çifti seç: ${pairLabel}`} />
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2 text-sm">
          <Link href={`/entities/${candidate.a.entity_id}`} className="font-medium text-foreground hover:underline">
            {candidate.a.name}
          </Link>
          {/* Yön OKU sistemin bir iddiası değil, yalnızca bir ayraç — ilişkinin yönünü de
              türünü de kullanıcı belirler. */}
          <span className="text-text-tertiary">—</span>
          <Link href={`/entities/${candidate.b.entity_id}`} className="font-medium text-foreground hover:underline">
            {candidate.b.name}
          </Link>
        </div>
        {candidate.shared_event_count > 0 && (
          <Badge variant="outline">{candidate.shared_event_count} ortak olay</Badge>
        )}
        <Badge variant="outline">{candidate.shared_claim_count} ortak claim</Badge>
        <Button size="sm" variant="outline" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
          {open ? "Vazgeç" : "Bağla"}
        </Button>
        <Button size="sm" variant="ghost" onClick={() => onDecide("REJECT")} disabled={busy}>
          İlgisiz
        </Button>
      </div>

      <div className="pl-7">
        <button
          type="button"
          onClick={() => setShowEvidence((v) => !v)}
          aria-expanded={showEvidence}
          className="flex items-center gap-1 text-[11px] font-medium text-text-secondary hover:text-foreground"
        >
          {showEvidence ? <ChevronDown aria-hidden className="h-3 w-3" /> : <ChevronRight aria-hidden className="h-3 w-3" />}
          Nerede birlikte geçiyor?
        </button>
        {showEvidence && (
          <div className="mt-1.5 flex flex-col gap-1">
            {candidate.shared_events.map((ev) => (
              <Link
                key={ev.id}
                href={`/events/${ev.id}`}
                className="text-xs text-text-secondary underline decoration-white/20 underline-offset-2 hover:text-foreground hover:decoration-white/50"
              >
                olay: {ev.title}
              </Link>
            ))}
            {candidate.evidence.map((e) => (
              <p key={e.claim_id} className="text-xs leading-relaxed text-pretty text-text-tertiary">
                <span className="font-mono text-[10px] text-text-secondary">{e.kinds}</span> — {e.excerpt}
              </p>
            ))}
          </div>
        )}
      </div>

      {open && (
        <div className="flex flex-wrap items-end gap-2 border-t border-border pt-2 pl-7">
          <div className="flex min-w-0 flex-1 flex-col gap-1.5">
            <Label htmlFor={`relation-type-${candidate.a.entity_id}-${candidate.b.entity_id}`}>
              {candidate.a.name} → ? → {candidate.b.name}
            </Label>
            <Input
              id={`relation-type-${candidate.a.entity_id}-${candidate.b.entity_id}`}
              value={relationType}
              onChange={(e) => setRelationType(e.target.value)}
              placeholder="ör. geliştirdi, sahibi, dava açtı"
            />
          </div>
          <Button onClick={() => onDecide("CREATE", relationType)} disabled={busy || !relationType.trim()}>
            <ArrowRight aria-hidden className="h-4 w-4" />
            Kur
          </Button>
        </div>
      )}
    </div>
  );
}
