"use client";

import { useMemo, useState } from "react";
import { AlertTriangle, ArrowRight, GitMerge, Layers, Link2, ShieldAlert, Zap } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import type {
  CandidateClaim,
  CandidateKind,
  ClaimLinkBatchResult,
  CorroborationCandidate,
} from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { ErrorState, EmptyState } from "@/components/ui/state";
import { SkeletonRows } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ConfidenceBadge } from "@/components/provenance/confidence";
import { useToast } from "@/components/ui/toast";
import { ConfirmButton } from "@/components/ui/confirm-button";

/** `SUPPORTED` eşiği — `confidence.py`'nin `SUPPORTED_THRESHOLD`'u. */
const SUPPORTED_THRESHOLD = 0.45;

type Tab = "corroboration" | "warnings";

const KIND_LABEL: Record<CandidateKind, string> = {
  CORROBORATION: "Bağımsız doğrulama",
  DERIVED_SUSPECT: "Türetme şüphesi",
  SHARED_ROOT: "Ortak kök",
  SAME_SOURCE_DUPLICATE: "Aynı kaynaktan yineleme",
};

/** Faz 17 — Corroboration Çalışma Ekranı.
 *
 * Faz 16 kuyruğu eritti ve şunu bıraktı: 44 claim'in 43'ü `REPORTED`, confidence 0.28–0.30'da
 * yığılmış. Sebep bir bug değil — tek kaynaklı bir claim `0.40 × güvenilirlik` alıyor, yani
 * `SUPPORTED` eşiği (0.45) tek kaynakla YAPISAL OLARAK erişilemez. Confidence'ın kalan %60'ı
 * (bağımsızlık + kanıt + doğrulama) 44 claim'de sıfır kez açıldı: mekanizma vardı, onu
 * tetikleyecek iş akışı yoktu.
 *
 * Bu ekran o akış. Faz 16'nın dersi birebir uygulanıyor: sorun "insan karar veriyor" değil,
 * kararın pahalı olması — bir claim'i doğrulayan diğerini bulmak 44 kaydı gözle taramak
 * demekti. */
export default function CorroborationPage() {
  const toast = useToast();
  const [tab, setTab] = useState<Tab>("corroboration");
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ClaimLinkBatchResult | null>(null);

  const { data: candidates, error, loading, reload } = useApi(
    () => api.claims.corroborationCandidates({ limit: 300 }),
    []
  );
  const { data: claims, reload: reloadClaims } = useApi(() => api.claims.list(), []);

  const corroboration = useMemo(
    () => (candidates ?? []).filter((c) => c.kind === "CORROBORATION"),
    [candidates]
  );
  const warnings = useMemo(
    () => (candidates ?? []).filter((c) => c.kind !== "CORROBORATION"),
    [candidates]
  );

  const shown = tab === "corroboration" ? corroboration : warnings;

  // Seçim türevi: görünür olmayan bir çift seçili SAYILMAZ (Faz 16'da kuyrukta alınan karar).
  const visibleKeys = useMemo(() => new Set(corroboration.map(pairKey)), [corroboration]);
  const activeSelection = useMemo(
    () => selected.filter((k) => visibleKeys.has(k)),
    [selected, visibleKeys]
  );

  function toggle(key: string, on: boolean) {
    setSelected((prev) => (on ? [...new Set([...prev, key])] : prev.filter((k) => k !== key)));
  }

  /** Faz 17 — uyarı kategorisinin eksik yarısı.
   *
   * Ekran yinelemeyi tespit ediyordu ama ne yapılacağını söylemiyordu; Faz 11/16'nın tekrar
   * eden dersi: bir sorunu görünür kılıp aksiyonunu vermemek işin yarısı. Yineleme SİLİNMEZ
   * (History Is Immutable) — eskisinin `valid_to`'su yenisinin `valid_from`'unda kapanır,
   * yani kayıt grafta durmaya devam eder ama artık iki kez sayılmaz. */
  async function closeDuplicate(candidate: CorroborationCandidate) {
    const [older, newer] = [candidate.claim_a, candidate.claim_b].sort(
      (x, y) => new Date(x.valid_from).getTime() - new Date(y.valid_from).getTime()
    );
    setBusy(true);
    try {
      await api.claims.addSupersede(newer.id, older.id);
      toast("Yineleme kapatıldı — eski kayıt silinmedi, geçerliliği sonlandı", "success");
      reload();
      reloadClaims();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Kapatma başarısız", "error");
    } finally {
      setBusy(false);
    }
  }

  async function link(pairs: CorroborationCandidate[], kind: "CORROBORATES" | "CONTRADICTS") {
    if (!pairs.length) return;
    setBusy(true);
    try {
      const res = await api.claims.linkBatch(
        pairs.map((p) => ({ claim_a_id: p.claim_a.id, claim_b_id: p.claim_b.id, link: kind }))
      );
      setResult(res);
      setSelected([]);
      toast(
        `${res.linked} bağ kuruldu` + (res.skipped ? ` · ${res.skipped} reddedildi` : ""),
        res.linked > 0 ? "success" : "default"
      );
      reload();
      reloadClaims();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Bağlama başarısız", "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <header>
        <h1 className="font-display text-[2rem] font-semibold tracking-tight text-foreground">
          Doğrulama
        </h1>
        <p className="max-w-2xl text-sm leading-relaxed text-text-secondary">
          Aynı olayı anlatan claim&apos;ler önerilir; bağımsız iki kaynak birbirini
          doğruladığında confidence yükselir. Tek kaynaklı bir iddia eşiği tek başına geçemez —
          confidence&apos;ın %40&apos;ı kaynaktan gelir, kalan %60 ancak burada açılır.
        </p>
      </header>

      {claims && <Scoreboard claims={claims} candidateCount={corroboration.length} />}

      <Tabs value={tab} onValueChange={(v) => v && setTab(v as Tab)}>
        <TabsList>
          <TabsTrigger value="corroboration">
            Doğrulama adayları{corroboration.length > 0 ? ` · ${corroboration.length}` : ""}
          </TabsTrigger>
          <TabsTrigger value="warnings">
            Uyarılar{warnings.length > 0 ? ` · ${warnings.length}` : ""}
          </TabsTrigger>
        </TabsList>
      </Tabs>

      {tab === "corroboration" && corroboration.length > 0 && (
        <div
          className={
            activeSelection.length
              ? "glass-panel sticky top-3 z-20 flex flex-wrap items-center gap-3 rounded-xl px-4 py-3"
              : "flex flex-wrap items-center gap-3 rounded-xl border border-border bg-surface px-4 py-3"
          }
        >
          <Checkbox
            checked={activeSelection.length === corroboration.length && corroboration.length > 0}
            indeterminate={activeSelection.length > 0 && activeSelection.length < corroboration.length}
            onCheckedChange={(on) => setSelected(on ? corroboration.map(pairKey) : [])}
            aria-label="Tüm doğrulama adaylarını seç"
          />
          <span className="text-sm text-text-secondary">
            {activeSelection.length ? (
              <>
                <strong className="tabular-nums text-foreground">{activeSelection.length}</strong> çift
                seçili
              </>
            ) : (
              <>
                <span className="tabular-nums text-foreground">{corroboration.length}</span> aday çift
              </>
            )}
          </span>
          <div className="ml-auto">
            <Button
              size="sm"
              disabled={!activeSelection.length || busy}
              onClick={() =>
                link(
                  corroboration.filter((c) => activeSelection.includes(pairKey(c))),
                  "CORROBORATES"
                )
              }
            >
              <Zap aria-hidden className="h-4 w-4" />
              Doğrular olarak bağla
            </Button>
          </div>
        </div>
      )}

      {result && <LinkResult result={result} onDismiss={() => setResult(null)} />}

      {loading && <SkeletonRows />}
      {error && <ErrorState message={error.message} onRetry={reload} />}
      {!loading && !error && shown.length === 0 && (
        <EmptyState
          title={tab === "corroboration" ? "Doğrulama adayı yok" : "Uyarı yok"}
          description={
            tab === "corroboration"
              ? "Aynı olayı anlatan, bağımsız kaynaklardan gelen bir claim çifti bulunamadı. Yeni içerik toplandıkça burası dolar."
              : "Türetilmiş kaynak ya da yinelenen kayıt tespit edilmedi."
          }
        />
      )}

      <div className="flex flex-col gap-3">
        {shown.map((candidate) => (
          <PairCard
            key={pairKey(candidate)}
            candidate={candidate}
            selected={activeSelection.includes(pairKey(candidate))}
            onToggle={(on) => toggle(pairKey(candidate), on)}
            onLink={(kind) => link([candidate], kind)}
            onCloseDuplicate={() => closeDuplicate(candidate)}
            busy={busy}
          />
        ))}
      </div>
    </div>
  );
}

function pairKey(c: CorroborationCandidate): string {
  return [c.claim_a.id, c.claim_b.id].sort().join("|");
}

/** Fazın karnesi: kaç claim eşiği geçti. Faz 16'nın kuyruk sağlığı şeridinin karşılığı —
 * ilerlemenin görünmediği bir iş akışı kullanılmaz. */
function Scoreboard({
  claims,
  candidateCount,
}: {
  claims: { confidence: number; knowledge_state: string; valid_to: string | null }[];
  candidateCount: number;
}) {
  const live = claims.filter((c) => !c.valid_to);
  const supported = live.filter((c) => c.confidence >= SUPPORTED_THRESHOLD).length;
  const reported = live.filter(
    (c) => c.confidence < SUPPORTED_THRESHOLD && c.knowledge_state !== "CONTRADICTED"
  ).length;
  const contradicted = live.filter((c) => c.knowledge_state === "CONTRADICTED").length;

  return (
    <div className="glass-panel grid grid-cols-2 gap-px overflow-hidden rounded-xl sm:grid-cols-4">
      <Stat label="Eşiği geçen" value={supported} tone="ok" />
      <Stat label="Tek kaynakta kalan" value={reported} tone="muted" />
      <Stat label="Çelişkili" value={contradicted} tone="warn" />
      <Stat label="Bekleyen aday" value={candidateCount} tone="accent" />
    </div>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "ok" | "muted" | "warn" | "accent";
}) {
  const toneClass =
    tone === "ok"
      ? "text-confidence-supported"
      : tone === "warn"
        ? "text-confidence-contradicted"
        : tone === "accent"
          ? "text-[var(--brand-accent)]"
          : "text-text-secondary";
  return (
    <div className="flex flex-col gap-0.5 bg-surface px-4 py-3">
      <span className="text-[11px] uppercase tracking-wide text-text-tertiary">{label}</span>
      <span className={`font-display text-2xl font-semibold tabular-nums ${toneClass}`}>{value}</span>
    </div>
  );
}

function PairCard({
  candidate,
  selected,
  onToggle,
  onLink,
  onCloseDuplicate,
  busy,
}: {
  candidate: CorroborationCandidate;
  selected: boolean;
  onToggle: (on: boolean) => void;
  onLink: (kind: "CORROBORATES" | "CONTRADICTS") => void;
  onCloseDuplicate: () => void;
  busy: boolean;
}) {
  const linkable = candidate.kind === "CORROBORATION";
  return (
    <div
      className={`flex flex-col gap-3 rounded-lg border bg-surface p-4 ${
        selected ? "border-[var(--brand-accent)]/50 bg-white/[0.07]" : "border-border"
      }`}
    >
      <div className="flex items-start gap-3">
        {linkable && (
          <div className="pt-0.5">
            <Checkbox checked={selected} onCheckedChange={onToggle} aria-label="Bu çifti seç" />
          </div>
        )}
        <KindBadge kind={candidate.kind} />
        <span className="ml-auto shrink-0 font-mono text-[11px] text-text-tertiary">
          sinyal {candidate.rare_overlap.toFixed(2)} · {candidate.days_apart.toFixed(1)} gün
        </span>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <ClaimSide claim={candidate.claim_a} projected={linkable ? candidate.projected_a : null} />
        <ClaimSide claim={candidate.claim_b} projected={linkable ? candidate.projected_b : null} />
      </div>

      <ul className="flex flex-col gap-1">
        {candidate.reasons.map((reason) => (
          <li key={reason} className="flex items-start gap-2 text-xs leading-relaxed text-text-secondary">
            <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-white/25" />
            {reason}
          </li>
        ))}
      </ul>

      <div className="flex flex-wrap items-center gap-2">
        {linkable ? (
          <Button size="sm" variant="outline" disabled={busy} onClick={() => onLink("CORROBORATES")}>
            <Link2 aria-hidden className="h-4 w-4" />
            Doğrular
          </Button>
        ) : (
          <p className="flex items-start gap-1.5 text-xs leading-relaxed text-priority-medium">
            <ShieldAlert aria-hidden className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            Doğrulama bağı kurulamaz — bağımsız kaynak değiller. API bunu yalnızca uyarmıyor,
            reddediyor.
          </p>
        )}
        {/* Çelişki her tür için açık: aynı kaynak kendi kendisiyle de çelişebilir ve bu
            değerli bir sinyaldir — bağımsızlık kısıtı yalnızca DOĞRULAMA için geçerli. */}
        <ConfirmButton
          onConfirm={() => onLink("CONTRADICTS")}
          confirmLabel="İki claim de CONTRADICTED olacak"
        >
          <GitMerge aria-hidden className="h-4 w-4" />
          Çelişir
        </ConfirmButton>
        {/* Yineleme yalnızca doğrulanamaz değil, ONARILABİLİR de olmalı: aynı haberin iki
            kaydı graf'ta iki ayrı iddia olarak duruyor. Kapatmak silmek değil — eskisinin
            geçerliliği yenisinin başladığı anda sonlanıyor (History Is Immutable). */}
        {(candidate.kind === "SAME_SOURCE_DUPLICATE" || candidate.kind === "SHARED_ROOT") && (
          <ConfirmButton
            onConfirm={onCloseDuplicate}
            confirmLabel="Eskisinin geçerliliği kapanacak, kayıt silinmeyecek"
          >
            <Layers aria-hidden className="h-4 w-4" />
            Yinelemeyi kapat
          </ConfirmButton>
        )}
      </div>
    </div>
  );
}

function ClaimSide({ claim, projected }: { claim: CandidateClaim; projected: number | null }) {
  const crosses = projected !== null && claim.confidence < SUPPORTED_THRESHOLD && projected >= SUPPORTED_THRESHOLD;
  return (
    <div className="flex min-w-0 flex-col gap-1.5 rounded-lg border border-border bg-black/20 p-3">
      <p className="text-sm text-foreground">{firstLine(claim.text)}</p>
      <p className="font-mono text-[11px] text-text-tertiary">
        {claim.source_name} · {new Date(claim.valid_from).toLocaleDateString("tr-TR")}
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <ConfidenceBadge state={claim.knowledge_state} confidence={claim.confidence} />
        {projected !== null && (
          <span
            className={`inline-flex items-center gap-1 font-mono text-[11px] tabular-nums ${
              crosses ? "text-confidence-supported" : "text-text-tertiary"
            }`}
          >
            <ArrowRight aria-hidden className="h-3 w-3" />
            {projected.toFixed(2)}
            {crosses && " · SUPPORTED"}
          </span>
        )}
      </div>
    </div>
  );
}

function KindBadge({ kind }: { kind: CandidateKind }) {
  if (kind === "CORROBORATION") {
    return (
      <Badge variant="secondary" className="gap-1">
        <Link2 aria-hidden className="h-3 w-3" />
        {KIND_LABEL[kind]}
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className="gap-1 border-priority-medium/40 text-priority-medium">
      <AlertTriangle aria-hidden className="h-3 w-3" />
      {KIND_LABEL[kind]}
    </Badge>
  );
}

function LinkResult({
  result,
  onDismiss,
}: {
  result: ClaimLinkBatchResult;
  onDismiss: () => void;
}) {
  const linked = result.results.filter((r) => r.status === "LINKED");
  const skipped = result.results.filter((r) => r.status === "SKIPPED");
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-surface p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-medium text-foreground">
          {result.linked} bağ kuruldu
          {result.skipped > 0 && ` · ${result.skipped} reddedildi`}
        </p>
        <Button size="sm" variant="ghost" onClick={onDismiss}>
          Kapat
        </Button>
      </div>

      {linked.length > 0 && (
        <ul className="flex flex-col gap-1">
          {linked.flatMap((r) =>
            Object.keys(r.confidence_after).map((claimId) => {
              const before = r.confidence_before[claimId] ?? 0;
              const after = r.confidence_after[claimId] ?? 0;
              const state = r.state_after[claimId];
              return (
                <li
                  key={`${r.claim_a_id}-${claimId}`}
                  className="flex items-center gap-2 font-mono text-[11px] tabular-nums text-text-secondary"
                >
                  <span className="text-text-tertiary">{claimId.slice(0, 8)}</span>
                  {before.toFixed(2)}
                  <ArrowRight aria-hidden className="h-3 w-3" />
                  <span className={after > before ? "text-confidence-supported" : ""}>
                    {after.toFixed(2)}
                  </span>
                  <span className="text-text-tertiary">{state}</span>
                </li>
              );
            })
          )}
        </ul>
      )}

      {skipped.length > 0 && (
        <ul className="flex flex-col gap-1.5">
          {skipped.map((r) => (
            <li key={`${r.claim_a_id}-${r.claim_b_id}`} className="text-xs leading-relaxed text-text-tertiary">
              {r.message}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function firstLine(text: string): string {
  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (trimmed) return trimmed.length > 120 ? `${trimmed.slice(0, 120)}…` : trimmed;
  }
  return "(boş claim)";
}
