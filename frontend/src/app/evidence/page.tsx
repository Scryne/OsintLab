"use client";

import { useMemo, useRef, useState } from "react";
import Link from "next/link";
import { Download, FileWarning, Fingerprint, Search, Upload } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import type { EvidenceVaultItem } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ErrorState, EmptyState } from "@/components/ui/state";
import { SkeletonRows } from "@/components/ui/skeleton";
import { TypeCombo } from "@/components/forms/type-combo";
import { ConfidenceBadge } from "@/components/provenance/confidence";
import { EvidenceClaimLinkDialog } from "@/components/forms/evidence-claim-link-dialog";
import { useToast } from "@/components/ui/toast";

// Öneri listesi — kural DEĞİL (bkz. TypeCombo).
const EVIDENCE_TYPE_SUGGESTIONS = [
  "fotoğraf", "video", "belge", "uydu görüntüsü", "ekran görüntüsü", "arşiv kaydı", "veri seti",
];

export default function EvidencePage() {
  const { data: items, error, loading, reload } = useApi(() => api.evidence.list(), []);
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    if (!items) return [];
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (e) =>
        e.evidence_type.toLowerCase().includes(q) ||
        (e.file_path ?? "").toLowerCase().includes(q) ||
        (e.content_hash ?? "").toLowerCase().includes(q) ||
        e.linked_claims.some((c) => c.headline.toLowerCase().includes(q))
    );
  }, [items, query]);

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <div>
        <h1 className="font-display text-[2rem] font-semibold tracking-tight text-foreground">Kanıt Kasası</h1>
        <p className="text-sm text-text-secondary">
          Yüklenen dosyalar içerik hash&apos;iyle (SHA-256) saklanır — aynı dosya iki kez
          kaydedilmez, sonradan değiştirilirse hash tutmaz.
        </p>
      </div>

      <UploadPanel onUploaded={reload} existingTypes={items?.map((e) => e.evidence_type) ?? []} />

      <div className="relative">
        <Search aria-hidden className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-tertiary" />
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Tür, dosya adı, hash veya bağlı claim ara…"
          className="pl-9"
        />
      </div>

      {loading && <SkeletonRows count={3} />}
      {error && <ErrorState message={error.message} onRetry={reload} />}
      {!loading && !error && filtered.length === 0 && (
        <EmptyState
          title={query ? "Eşleşen kanıt yok" : "Kasa boş"}
          description={query ? undefined : "Yukarıdan bir dosya yükleyerek başla."}
        />
      )}

      <div className="flex flex-col gap-2">
        {filtered.map((item) => (
          <EvidenceRow key={item.id} item={item} onChanged={reload} />
        ))}
      </div>
    </div>
  );
}

function UploadPanel({
  onUploaded,
  existingTypes,
}: {
  onUploaded: () => void;
  existingTypes: string[];
}) {
  const toast = useToast();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [evidenceType, setEvidenceType] = useState(EVIDENCE_TYPE_SUGGESTIONS[0]);
  const [submitting, setSubmitting] = useState(false);

  async function submit() {
    if (!file) return;
    setSubmitting(true);
    try {
      await api.evidence.upload({ file, evidence_type: evidenceType });
      toast(`${file.name} kasaya eklendi`, "success");
      setFile(null);
      if (inputRef.current) inputRef.current.value = "";
      onUploaded();
    } catch (err) {
      // 409 (aynı dosya zaten kayıtlı) burada hata gibi görünür ama aslında bilgilendirme —
      // mesaj mevcut kanıtın id'sini söylüyor, kullanıcı onu claim'e bağlayabilir.
      toast(err instanceof Error ? err.message : "Yüklenemedi", "error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="evidence-file">Dosya</Label>
          <Input
            id="evidence-file"
            ref={inputRef}
            type="file"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="file:mr-3 file:rounded-md file:border-0 file:bg-white/10 file:px-2.5 file:py-1 file:text-xs file:text-foreground"
          />
          <p className="text-xs text-text-tertiary">En fazla 50 MB.</p>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="evidence-type">Tür</Label>
          <TypeCombo
            id="evidence-type"
            value={evidenceType}
            onChange={setEvidenceType}
            suggestions={[...EVIDENCE_TYPE_SUGGESTIONS, ...existingTypes]}
            placeholder="ör. belge, ekran görüntüsü"
          />
        </div>
      </div>
      <Button onClick={submit} disabled={submitting || !file} className="self-start">
        <Upload aria-hidden className="h-4 w-4" />
        {submitting ? "Yükleniyor…" : "Kasaya ekle"}
      </Button>
    </div>
  );
}

/** Vault'a yüklenen dosyanın yolu: `<2hex>/<16hex>-<özgün ad>`. Yalnızca bu kalıba uyan bir
 * yoldan hash öneki kırpılır — `file_path` elle de doldurulabiliyor ve orada çoğu zaman bir
 * URL duruyor. Kalıbı kontrol etmeden kırpmak, "…/liman-ihalesi" adresini "ihalesi" diye
 * göstermek demekti (ilk görsel doğrulamada böyle çıktı). */
const STORED_FILE_RE = /^[0-9a-f]{2}\/[0-9a-f]{16}-(.+)$/;

function EvidenceRow({ item, onChanged }: { item: EvidenceVaultItem; onChanged: () => void }) {
  const stored = item.file_path?.match(STORED_FILE_RE);
  const displayName = stored ? stored[1] : item.file_path;

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge variant="secondary">{item.evidence_type}</Badge>
            {/* Dosyası olmayan kanıt gizlenmiyor, işaretleniyor: elle girilmiş bir yol ya da
                taşınmış bir dosya olabilir — sessizce "indirilebilir" göstermek yanıltırdı. */}
            {!item.has_file && (
              <Badge variant="secondary" className="text-priority-medium">
                <FileWarning aria-hidden className="h-3 w-3" />
                dosya yok
              </Badge>
            )}
          </div>
          <p className="mt-1 break-all text-sm text-foreground">
            {displayName ?? <span className="text-text-tertiary">(dosya adı yok)</span>}
          </p>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-text-tertiary">
            <span className="font-mono">
              {new Date(item.collected_at ?? item.created_at).toLocaleDateString("tr-TR")}
            </span>
            {item.content_hash && (
              <span className="inline-flex items-center gap-1 font-mono" title={item.content_hash}>
                <Fingerprint aria-hidden className="h-3 w-3" />
                {item.content_hash.slice(0, 12)}…
              </span>
            )}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {item.has_file && (
            <Button
              size="sm"
              variant="outline"
              className="h-7 px-2 text-xs"
              // Base UI, <button> dışında bir eleman render edilirken bunu istiyor —
              // aksi halde native buton semantiği sessizce kayboluyor (erişilebilirlik).
              nativeButton={false}
              render={
                <a href={api.evidence.fileUrl(item.id)} download>
                  <Download aria-hidden className="h-3.5 w-3.5" />
                  İndir
                </a>
              }
            />
          )}
          <EvidenceClaimLinkDialog evidenceId={item.id} onLinked={onChanged} />
        </div>
      </div>

      <div className="mt-3 border-t border-border pt-3">
        {item.linked_claims.length === 0 ? (
          <p className="text-xs text-text-tertiary">
            Hiçbir claim&apos;e bağlı değil — bu haliyle confidence hesabına girmiyor.
          </p>
        ) : (
          <ul className="flex flex-col gap-1.5">
            {item.linked_claims.map((c) => (
              <li key={`${c.claim_id}-${c.stance}`} className="flex flex-wrap items-center gap-2 text-xs">
                <Badge variant={c.stance === "CONTRADICTS" ? "destructive" : "outline"}>
                  {c.stance === "CONTRADICTS" ? "çürütüyor" : "destekliyor"}
                </Badge>
                <ConfidenceBadge state={c.knowledge_state} confidence={c.confidence} />
                <span className="min-w-0 flex-1 truncate text-text-secondary">{c.headline}</span>
                {c.source_id && (
                  <Link
                    href={`/sources/${c.source_id}`}
                    className="shrink-0 text-text-tertiary underline decoration-white/20 underline-offset-2 hover:text-foreground"
                  >
                    {c.source_name} →
                  </Link>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
