"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Check, X } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import type { ClaimMentionGroup } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { EmptyState, ErrorState } from "@/components/ui/state";
import { SkeletonRows } from "@/components/ui/skeleton";
import { ConfidenceBadge } from "@/components/provenance/confidence";
import { useToast } from "@/components/ui/toast";

type Decision = { claim_id: string; entity_id: string; action: "CONFIRM" | "REJECT"; matched_on: string };

const pairKey = (claimId: string, entityId: string) => `${claimId}::${entityId}`;

/** Faz 21 — Claim ↔ Entity çoklu bağ.
 *
 * Ölçüm (2026-09-08): 58 entity'nin 52'si claim metinlerinde geçiyordu ve hiçbirinin bir
 * claim bağı yoktu. Sebep ilgisizlik değil, `ABOUT_ENTITY`nin tekil kullanılması: bir claim
 * yalnızca tek bir şey "hakkında" olabiliyordu, oysa gerçek bir claim ortalama 2.48
 * entity'ye değiyor. Ölçülen 134 değmenin en fazla 54'ü graf'a girebiliyordu.
 *
 * Bu ekran o farkı kapatıyor. Karar claim ekseninde gruplu, çünkü orada ucuz: metne bir kez
 * bakıp "evet bu üçü de geçiyor" demek, aynı üç çifti üç ayrı satırda değerlendirmekten
 * hızlıdır (Faz 16'nın dersi).
 */
export default function MentionsPage() {
  const toast = useToast();
  const { data, error, loading, reload } = useApi(() => api.claims.mentionCandidates(), []);
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  const groups = useMemo(() => data ?? [], [data]);
  const allPairs = useMemo(
    () => groups.flatMap((g) => g.candidates.map((c) => pairKey(g.claim_id, c.entity_id))),
    [groups]
  );
  const visible = useMemo(() => new Set(allPairs), [allPairs]);
  const activeSelection = useMemo(() => selected.filter((k) => visible.has(k)), [selected, visible]);

  const pairIndex = useMemo(() => {
    const map = new Map<string, Decision>();
    for (const g of groups) {
      for (const c of g.candidates) {
        map.set(pairKey(g.claim_id, c.entity_id), {
          claim_id: g.claim_id,
          entity_id: c.entity_id,
          action: "CONFIRM",
          matched_on: c.matched_on,
        });
      }
    }
    return map;
  }, [groups]);

  async function decide(keys: string[], action: "CONFIRM" | "REJECT") {
    if (keys.length === 0) return;
    const decisions = keys
      .map((k) => pairIndex.get(k))
      .filter((d): d is Decision => Boolean(d))
      .map((d) => ({ ...d, action }));
    setBusy(true);
    try {
      const res = await api.claims.decideMentions(decisions);
      toast(
        action === "CONFIRM" ? `${res.confirmed} bağ kuruldu` : `${res.rejected} öneri reddedildi`,
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

  const pairCount = allPairs.length;

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <header>
        <h1 className="font-display text-[2rem] font-semibold tracking-tight text-balance text-foreground">
          Bağ Adayları
        </h1>
        <p className="max-w-2xl text-sm leading-relaxed text-text-secondary">
          Bir claim yalnızca tek bir şey <em>hakkında</em> olabilir, ama birden çok şeye
          <em> değebilir</em>. Aşağıdaki adaylar claim metninde adı geçen entity&apos;ler.
          Onaylananlar o entity&apos;nin sayfasında ve vault notunda görünür — ama iddianın
          öznesi olarak değil, adı geçen kayıt olarak.
        </p>
      </header>

      {pairCount > 0 && (
        <div
          className={
            activeSelection.length
              ? "glass-panel sticky top-3 z-20 flex flex-wrap items-center gap-3 rounded-xl px-4 py-3"
              : "flex flex-wrap items-center gap-3 rounded-xl border border-border bg-surface px-4 py-3"
          }
        >
          <Checkbox
            checked={activeSelection.length === pairCount && pairCount > 0}
            indeterminate={activeSelection.length > 0 && activeSelection.length < pairCount}
            onCheckedChange={(on) => setSelected(on ? allPairs : [])}
            aria-label="Tüm bağ adaylarını seç"
          />
          <span className="text-sm text-text-secondary">
            {activeSelection.length ? (
              <>
                <strong className="tabular-nums text-foreground">{activeSelection.length}</strong> bağ seçili
              </>
            ) : (
              <>
                <span className="tabular-nums text-foreground">{pairCount}</span> aday bağ ·{" "}
                {groups.length} claim
              </>
            )}
          </span>
          <div className="ml-auto flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => decide(activeSelection, "REJECT")}
              disabled={busy || activeSelection.length === 0}
            >
              <X aria-hidden className="h-4 w-4" />
              Reddet
            </Button>
            <Button size="sm" onClick={() => decide(activeSelection, "CONFIRM")} disabled={busy || activeSelection.length === 0}>
              <Check aria-hidden className="h-4 w-4" />
              Bağla
            </Button>
          </div>
        </div>
      )}

      {loading && <SkeletonRows />}
      {error && <ErrorState error={error} onRetry={reload} />}
      {!loading && !error && pairCount === 0 && (
        <EmptyState
          title="Bekleyen bağ adayı yok"
          description="Liste eritilmiş. Yeni claim'ler eklendikçe ya da yeni entity onaylandıkça yeni adaylar burada belirir."
        />
      )}

      <div className="flex flex-col gap-3">
        {groups.map((group) => (
          <ClaimGroup
            key={group.claim_id}
            group={group}
            selected={selected}
            onToggle={(key, on) =>
              setSelected((prev) => (on ? [...new Set([...prev, key])] : prev.filter((k) => k !== key)))
            }
            onDecide={decide}
            busy={busy}
          />
        ))}
      </div>
    </div>
  );
}

function ClaimGroup({
  group,
  selected,
  onToggle,
  onDecide,
  busy,
}: {
  group: ClaimMentionGroup;
  selected: string[];
  onToggle: (key: string, on: boolean) => void;
  onDecide: (keys: string[], action: "CONFIRM" | "REJECT") => void;
  busy: boolean;
}) {
  const keys = group.candidates.map((c) => pairKey(group.claim_id, c.entity_id));
  const lines = group.text.split("\n").filter((l) => l.trim());

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-surface p-4">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <ConfidenceBadge state={group.knowledge_state} confidence={group.confidence} />
          {group.source_name && <span className="text-xs text-text-tertiary">{group.source_name}</span>}
          {/* Öznesi olmayan claim'ler Faz 18'de olaya bağlananlar; bunu söylemek şart,
              yoksa "özne yok" bir eksiklik gibi okunur. */}
          <span className="text-xs text-text-tertiary">
            {group.subject_name ? `öznesi: ${group.subject_name}` : "öznesi bir olay"}
          </span>
        </div>
        {/* Q22: toplanan içerik veri, talimat değil — burada yalnızca okunuyor. */}
        <p className="mt-1.5 text-sm font-medium text-pretty text-foreground">{lines[0]}</p>
        {lines[1] && <p className="mt-1 text-xs leading-relaxed text-pretty text-text-tertiary">{lines[1]}</p>}
      </div>

      <ul className="flex flex-wrap gap-2">
        {group.candidates.map((c) => {
          const key = pairKey(group.claim_id, c.entity_id);
          const checked = selected.includes(key);
          return (
            <li
              key={key}
              className="flex items-center gap-2 rounded-lg border border-border bg-surface-raised/40 px-2.5 py-1.5"
            >
              <Checkbox
                checked={checked}
                onCheckedChange={(on) => onToggle(key, Boolean(on))}
                aria-label={`Bağ adayı: ${c.name}`}
              />
              <Link href={`/entities/${c.entity_id}`} className="text-sm text-foreground hover:underline">
                {c.name}
              </Link>
              <Badge variant="outline">{c.entity_type}</Badge>
              {/* Eşleşme adın kendisi olmayabilir: Faz 20'de kurulan alias'lar üzerinden de
                  gelebilir ("GPT-6 Astra" → Astra). Hangisi olduğu söylenmezse öneri
                  denetlenemez hale gelir. */}
              {c.matched_on !== c.name && (
                <span className="font-mono text-[10px] text-text-tertiary">“{c.matched_on}”</span>
              )}
            </li>
          );
        })}
      </ul>

      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" variant="outline" onClick={() => onDecide(keys, "CONFIRM")} disabled={busy}>
          <Check aria-hidden className="h-4 w-4" />
          Hepsini bağla ({keys.length})
        </Button>
        <Button size="sm" variant="ghost" onClick={() => onDecide(keys, "REJECT")} disabled={busy}>
          Hepsini reddet
        </Button>
      </div>
    </div>
  );
}
