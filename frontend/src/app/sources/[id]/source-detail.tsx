"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowUp, Bell, BellOff, ExternalLink, GitBranch, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import type { Source } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { LoadingState, ErrorState, EmptyState } from "@/components/ui/state";
import { ConfidenceBadge } from "@/components/provenance/confidence";
import { LineageDialog } from "@/components/forms/lineage-dialog";
import { ScanScheduleList } from "@/components/forms/scan-schedules";
import { useToast } from "@/components/ui/toast";

export function SourceDetail({ sourceId }: { sourceId: string }) {
  const toast = useToast();
  const { data: source, error, loading } = useApi(() => api.sources.get(sourceId), [sourceId]);
  const { data: allSources } = useApi(() => api.sources.list(), []);
  const { data: lineage, reload: reloadLineage } = useApi(() => api.sources.lineage(sourceId), [sourceId]);
  const { data: claims } = useApi(() => api.sources.claims(sourceId), [sourceId]);

  // undefined = henüz bilinmiyor (butonu kilitler), null = izlenmiyor.
  const [monitor, setMonitor] = useState<{ id: string } | null | undefined>(undefined);
  useEffect(() => {
    let cancelled = false;
    api.monitors
      .list(true)
      .then((monitors) => {
        if (cancelled) return;
        setMonitor(monitors.find((m) => m.target_type === "Source" && m.target_id === sourceId) ?? null);
      })
      .catch(() => {
        if (!cancelled) setMonitor(null);
      });
    return () => {
      cancelled = true;
    };
  }, [sourceId]);

  async function toggleMonitor() {
    try {
      if (monitor) {
        await api.monitors.delete(monitor.id);
        setMonitor(null);
        toast("İzleme kapatıldı — bu kaynağın taramaları artık Inbox'a düşmez", "default");
      } else {
        const created = await api.monitors.create({ target_type: "Source", target_id: sourceId });
        setMonitor(created);
        toast("İzlemeye alındı", "success");
      }
    } catch (err) {
      toast(err instanceof Error ? err.message : "İşlem başarısız", "error");
    }
  }

  if (loading) return <LoadingState label="Kaynak yükleniyor…" />;
  if (error) return <ErrorState message={error.message} />;
  if (!source) return null;

  const ancestors = lineage?.ancestors ?? [];
  const descendants = lineage?.descendants ?? [];
  const isDerived = ancestors.length > 0;

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="font-display text-[2rem] font-semibold tracking-tight text-foreground">
              {source.name}
            </h1>
            <Badge variant="secondary">{source.source_type}</Badge>
          </div>
          <p className="mt-1 text-sm text-text-secondary">
            <span className="tabular-nums">Güvenilirlik %{Math.round(source.reliability * 100)}</span>
            {" · "}
            {isDerived ? (
              <span className="text-priority-medium-text">Türetilmiş kaynak ({ancestors.length} üst kaynak)</span>
            ) : (
              <span>Bağımsız kaynak</span>
            )}
          </p>
          {source.url && (
            <a
              href={source.url}
              target="_blank"
              rel="noreferrer"
              className="mt-1 inline-flex items-center gap-1 font-mono text-xs text-text-secondary underline decoration-white/20 underline-offset-2 hover:text-foreground hover:decoration-white/50"
            >
              {source.url}
              <ExternalLink aria-hidden className="h-3 w-3" />
            </a>
          )}
          <p className="mt-1 font-mono text-xs text-text-tertiary">
            {new Date(source.created_at).toLocaleString("tr-TR")} tarihinde eklendi
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 lg:shrink-0">
          <LineageDialog source={source} allSources={allSources ?? []} onChanged={reloadLineage} />
          <Button
            variant={monitor ? "secondary" : "outline"}
            size="sm"
            onClick={toggleMonitor}
            disabled={monitor === undefined}
          >
            {monitor ? <Bell aria-hidden className="h-4 w-4" /> : <BellOff aria-hidden className="h-4 w-4" />}
            {monitor ? "İzleniyor" : "İzlemeye al"}
          </Button>
        </div>
      </header>

      {/* Varsayılan sekme Claim'ler: kaynakların çoğunda hiç lineage kenarı yok (gerçek
          graftaki 5 kaynağın hiçbirinde), lineage'i varsayılan yapmak kullanıcıyı boş bir
          ekranla karşılardı. Zincir bir tık uzakta ve sekme sayısı kaç bağ olduğunu söylüyor. */}
      <Tabs defaultValue="claims">
        <div className="overflow-x-auto">
          <TabsList className="w-max">
            <TabsTrigger value="lineage">Lineage ({ancestors.length + descendants.length})</TabsTrigger>
            <TabsTrigger value="claims">Claim&apos;ler ({claims?.length ?? 0})</TabsTrigger>
            <TabsTrigger value="scans">Otomatik Tarama</TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="lineage" className="mt-4">
          <LineagePanel
            source={source}
            ancestors={ancestors}
            descendants={descendants}
            rootId={lineage?.independent_root_id ?? null}
          />
        </TabsContent>

        <TabsContent value="claims" className="mt-4">
          <ClaimsPanel claims={claims ?? []} />
        </TabsContent>

        <TabsContent value="scans" className="mt-4">
          <ScanScheduleList
            sourceId={sourceId}
            emptyText="Bu kaynak için zamanlanmış tarama yok. Toplayıcılar sayfasından kurabilirsin."
          />
          {monitor === null && (
            <p className="mt-3 text-xs text-priority-medium-text">
              Bu kaynak izlenmiyor — taramalar çalışsa bile Inbox&apos;a hiçbir şey düşmez. Yukarıdaki
              &quot;İzlemeye al&quot; ile açabilirsin.
            </p>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

type LineageNode = { id: string; name: string; url: string | null; depth: number };

/** Faz 6'nın Source Independence grafiği, ilk kez arayüzde. Zincir olarak gösterilebilmesi
 * `depth`e bağlı — backend'in bunu döndürmesi Faz 13'te eklendi (öncesinde sıra tanımsızdı).
 *
 * Neden sadece bir liste değil: lineage'in confidence üzerinde doğrudan etkisi var. İki haber
 * aynı ajanstan türemişse birbirini "bağımsız olarak" doğrulamıyor — Q4 formülündeki
 * independence terimi düşüyor. Kullanıcının bir corroboration'a bakarken bunu görebilmesi
 * gerekiyor. */
function LineagePanel({
  source,
  ancestors,
  descendants,
  rootId,
}: {
  source: Source;
  ancestors: LineageNode[];
  descendants: LineageNode[];
  rootId: string | null;
}) {
  if (ancestors.length === 0 && descendants.length === 0) {
    return (
      <EmptyState
        title="Bilinen bir türetme ilişkisi yok"
        description="Bu kaynak şu an bağımsız sayılıyor: attığı claim'ler confidence hesabında tam independence puanı alıyor. Bir haberin başka bir kaynaktan alındığını fark edersen yukarıdaki Lineage butonuyla bağla."
      />
    );
  }

  // Tek sürekli kolon: üstteki en uzak ata, en altta en uzak türev, ortada bu kaynak.
  // İki ayrı bölüm ("türediği" / "türeyenler") olarak çizmek zinciri ikiye bölüyordu ve
  // aradaki bağ görünmüyordu — oysa okunması gereken şey tam olarak o tek hat.
  const chain: (LineageNode & { role: "ancestor" | "self" | "descendant" })[] = [
    ...[...ancestors].reverse().map((n) => ({ ...n, role: "ancestor" as const })),
    { id: source.id, name: source.name, url: source.url, depth: 0, role: "self" as const },
    ...descendants.map((n) => ({ ...n, role: "descendant" as const })),
  ];

  // Aynı derinlikte birden fazla kaynak varsa bu bir zincir değil, dallanan bir ağaç —
  // tek kolonda göstermek onu olduğundan düz gösterirdi, o yüzden açıkça söylüyoruz.
  const branching = ["ancestor", "descendant"].some((role) => {
    const depths = chain.filter((n) => n.role === role).map((n) => n.depth);
    return new Set(depths).size !== depths.length;
  });

  return (
    <div className="flex flex-col gap-4">
      <p className="text-xs text-text-tertiary">
        Ok yönü <strong className="text-text-secondary">&quot;şundan türetildi&quot;</strong>{" "}
        demek — yukarı doğru gidildikçe bilginin asıl kaynağına yaklaşılır.
      </p>

      <div className="flex flex-col">
        {chain.map((node, i) => (
          <div key={node.id}>
            {i > 0 && <ChainArrow />}
            {node.role === "self" ? (
              <SelfNode name={node.name} />
            ) : (
              <ChainNode node={node} isRoot={node.id === rootId} />
            )}
          </div>
        ))}
      </div>

      {branching && (
        <p className="text-xs text-priority-medium-text">
          Aynı seviyede birden fazla kaynak var — bu düz bir zincir değil, dallanan bir ağaç.
          Yukarıdaki liste hop sayısına göre sıralı, ama yan yana duran iki kaynak birbirinin
          devamı olmayabilir.
        </p>
      )}

      <p className="text-xs text-text-tertiary">
        Türetilmiş kaynaklar birbirini <strong className="text-text-secondary">bağımsız olarak
        doğrulamaz</strong>: aynı köke dayanan iki haber, confidence formülündeki independence
        terimini yükseltmez (Q4/Faz 6).
      </p>
    </div>
  );
}

function ChainNode({ node, isRoot }: { node: LineageNode & { role: string }; isRoot: boolean }) {
  return (
    <Link
      href={`/sources/${node.id}`}
      className="flex items-center justify-between gap-2 rounded-lg border border-border bg-surface px-3 py-2 transition-colors hover:border-white/20"
    >
      <span className="min-w-0 truncate">
        <span className="text-sm text-foreground">{node.name}</span>
        {node.url && <span className="ml-2 font-mono text-xs text-text-tertiary">{node.url}</span>}
      </span>
      <span className="flex shrink-0 items-center gap-1.5">
        {isRoot && (
          <Badge variant="outline">
            <ShieldCheck aria-hidden className="h-3 w-3" />
            bağımsız kök
          </Badge>
        )}
        <Badge variant="secondary" className="tabular-nums">
          {node.depth} hop {node.role === "ancestor" ? "yukarı" : "aşağı"}
        </Badge>
      </span>
    </Link>
  );
}

function ChainArrow() {
  return (
    <div className="flex justify-center py-1 text-text-tertiary" aria-hidden>
      <ArrowUp className="h-3.5 w-3.5" />
    </div>
  );
}

function SelfNode({ name }: { name: string }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-white/20 bg-surface-raised px-3 py-2">
      <GitBranch aria-hidden className="h-4 w-4 text-text-tertiary" />
      <span className="truncate text-sm font-medium text-foreground">{name}</span>
      <Badge variant="outline" className="shrink-0">bu kaynak</Badge>
    </div>
  );
}

function ClaimsPanel({
  claims,
}: {
  claims: {
    id: string;
    text: string;
    knowledge_state: string;
    confidence: number;
    valid_from: string;
    about_entity_id: string | null;
    about_entity_name: string | null;
    about_event_id: string | null;
    about_event_title: string | null;
    superseded_by_claim_id: string | null;
  }[];
}) {
  if (claims.length === 0) {
    return (
      <EmptyState
        title="Bu kaynak henüz bir claim atfetmedi"
        description="Bir gözlemi promote ettiğinde ya da elle claim eklediğinde burada görünür."
      />
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {claims.map((claim) => {
        // F34: yerini almış bir claim, güncel olanla birebir aynı görünmemeli.
        const superseded = Boolean(claim.superseded_by_claim_id);
        const headline = claim.text.split("\n").find((l) => l.trim()) ?? claim.text;
        return (
          <div
            key={claim.id}
            className={`rounded-lg border border-border bg-surface p-4 ${superseded ? "opacity-60" : ""}`}
          >
            <div className="flex flex-wrap items-center gap-2">
              <ConfidenceBadge
                state={claim.knowledge_state as never}
                confidence={claim.confidence}
              />
              {superseded && <Badge variant="secondary">yerini aldı: daha yeni bir claim</Badge>}
              {!claim.about_entity_id && !claim.about_event_id && (
                <Badge variant="secondary" className="text-priority-medium-text">
                  hiçbir şeye bağlı değil
                </Badge>
              )}
            </div>
            <p className={`mt-1.5 text-sm text-foreground ${superseded ? "line-through decoration-white/30" : ""}`}>
              {headline}
            </p>
            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-text-tertiary">
              <span className="font-mono">{new Date(claim.valid_from).toLocaleDateString("tr-TR")}</span>
              {claim.about_entity_id && (
                <Link
                  href={`/entities/${claim.about_entity_id}`}
                  className="text-text-secondary underline decoration-white/20 underline-offset-2 hover:text-foreground"
                >
                  {claim.about_entity_name} →
                </Link>
              )}
              {claim.about_event_id && (
                <Link
                  href={`/events/${claim.about_event_id}`}
                  className="text-text-secondary underline decoration-white/20 underline-offset-2 hover:text-foreground"
                >
                  {claim.about_event_title} →
                </Link>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
