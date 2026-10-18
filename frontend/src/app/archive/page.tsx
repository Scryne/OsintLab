"use client";

import { useMemo, useState } from "react";
import { Archive, CheckCircle2, ExternalLink, FileText, Loader2, RefreshCw, ShieldAlert, ShieldQuestion } from "lucide-react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import type { ArchiveRecord, ArchiveStatus } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { EmptyState, ErrorState } from "@/components/ui/state";
import { SkeletonRows } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ConfidenceBadge } from "@/components/provenance/confidence";
import { useToast } from "@/components/ui/toast";

type Filtre = "hepsi" | ArchiveStatus;

const FILTRELER: { value: Filtre; label: string }[] = [
  { value: "hepsi", label: "Hepsi" },
  { value: "DOGRULANDI", label: "Doğrulandı" },
  { value: "DEGISMIS", label: "Değişmiş" },
  { value: "ERISILEMEDI", label: "Erişilemedi" },
  { value: "ARSIVLENDI", label: "Bakılmadı" },
];

// Renk burada bilgi taşıyor (DESIGN.md kontrast sözleşmesi): metin için ham rampa rengi
// değil `-text` varyantı kullanılıyor. "Değişmiş" kritik değil UYARIDIR — kaynak ölmedi,
// içeriği kaydı; erişilemeyen bir kaynakla aynı renge boyansaydı ikisi de anlamını yitirirdi.
const DURUM_GORUNUMU: Record<ArchiveStatus, { kisa: string; icon: typeof CheckCircle2; sinif: string }> = {
  DOGRULANDI: { kisa: "Doğrulandı", icon: CheckCircle2, sinif: "border-confidence-supported/40 text-confidence-supported-text" },
  DEGISMIS: { kisa: "Değişmiş", icon: ShieldAlert, sinif: "border-priority-high/40 text-priority-high-text" },
  ERISILEMEDI: { kisa: "Erişilemedi", icon: ShieldAlert, sinif: "border-priority-critical/40 text-priority-critical-text" },
  ARSIVLENDI: { kisa: "Bakılmadı", icon: ShieldQuestion, sinif: "border-border text-text-secondary" },
};

function host(url: string | null): string {
  if (!url) return "—";
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

/** Faz 26 — Kaynak Arşivi.
 *
 * Bir iddianın dayanağı bugüne kadar yalnızca bir bağlantıydı. Sayfa değişir ya da silinirse
 * elimizde hiçbir şey kalmıyordu — "History Is Immutable" ilkesi tam bu noktada karşılıksızdı.
 * Artık her promote, dayanılan metnin kopyasını (hash + URL + toplama zamanı) saklıyor.
 *
 * Sayfanın taşıdığı ayrım: **arşiv bir KAYIT, doğrulama bir KANITTIR.** Arşiv otomatik oluşur
 * ve confidence'a hiç dokunmaz; skora ancak canlı sayfaya karşı doğrulandığında girer. İkisi
 * karıştırılsaydı her claim kendi kaynağının kopyasıyla "kanıtlı" sayılır, kanıt alt-skoru
 * kaynak kalitesinin bir kopyasına dönerdi.
 */
export default function ArchivePage() {
  const toast = useToast();
  const [filtre, setFiltre] = useState<Filtre>("hepsi");
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  const { data: records, error, loading, reload } = useApi(() => api.archive.list(), []);
  const { data: pending, reload: reloadPending } = useApi(() => api.archive.pending(), []);

  const hepsi = useMemo(() => records ?? [], [records]);
  const sayim = useMemo(() => {
    const s: Record<string, number> = { DOGRULANDI: 0, DEGISMIS: 0, ERISILEMEDI: 0, ARSIVLENDI: 0 };
    for (const r of hepsi) s[r.archive_status] = (s[r.archive_status] ?? 0) + 1;
    return s;
  }, [hepsi]);
  const skorlanan = useMemo(() => hepsi.filter((r) => r.scored).length, [hepsi]);

  const gosterilen = useMemo(
    () => (filtre === "hepsi" ? hepsi : hepsi.filter((r) => r.archive_status === filtre)),
    [hepsi, filtre]
  );
  // Görünür olmayan bir kayıt seçili sayılmaz — Faz 16 kuyruğunda alınan kararın aynısı:
  // ekranda olmayan bir şeye toplu işlem uygulamak sürpriz olurdu.
  const gorunurIds = useMemo(() => new Set(gosterilen.map((r) => r.claim_id)), [gosterilen]);
  const secim = useMemo(() => selected.filter((id) => gorunurIds.has(id)), [selected, gorunurIds]);

  function yenile() {
    reload();
    reloadPending();
  }

  async function geriDoldur() {
    setBusy(true);
    try {
      const res = await api.archive.create();
      toast(`${res.created} arşiv kopyası oluşturuldu`, "success");
      yenile();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Arşivleme başarısız", "error");
    } finally {
      setBusy(false);
    }
  }

  async function dogrula(ids: string[]) {
    if (ids.length === 0) return;
    setBusy(true);
    try {
      const res = await api.archive.verify(ids);
      const durum = res.state_changes > 0 ? ` — ${res.state_changes} claim durum değiştirdi` : "";
      toast(
        `${res.checked} arşiv kontrol edildi: ${res.verified} doğrulandı, ${res.changed} değişmiş, ${res.unreachable} erişilemedi${durum}`,
        res.unreachable > 0 || res.changed > 0 ? "default" : "success"
      );
      setSelected([]);
      yenile();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Doğrulama başarısız", "error");
    } finally {
      setBusy(false);
    }
  }

  const bekleyen = pending?.length ?? 0;

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <header>
        <h1 className="font-display text-[2rem] font-semibold tracking-tight text-balance text-foreground">
          Kaynak Arşivi
        </h1>
        <p className="max-w-2xl text-sm leading-relaxed text-text-secondary">
          Her iddia, dayandığı metnin bir kopyasıyla birlikte saklanıyor — kaynak sayfa
          silinse de elde kalan kayıt bu. Arşivin kendisi confidence&apos;a dokunmaz: bir
          arşiv, kaynağın o cümleyi <em>söylediğinin</em> kaydıdır, iddianın doğru olduğunun
          kanıtı değil. Skora ancak canlı sayfaya karşı doğrulandığında girer.
        </p>
      </header>

      <div className="flex flex-wrap items-center gap-4 rounded-xl border border-border bg-surface px-4 py-3 text-sm">
        <span className="text-text-secondary">
          <strong className="tabular-nums text-foreground">{hepsi.length}</strong> arşiv
        </span>
        <span className="text-text-secondary">
          <strong className="tabular-nums text-confidence-supported-text">{skorlanan}</strong> skora giriyor
        </span>
        <span className="text-text-secondary">
          <strong className="tabular-nums text-foreground">{sayim.ARSIVLENDI}</strong> henüz bakılmadı
        </span>
        {bekleyen > 0 && (
          <span className="text-text-secondary">
            <strong className="tabular-nums text-foreground">{bekleyen}</strong> claim&apos;in arşivi yok
          </span>
        )}
        <div className="ml-auto flex items-center gap-2">
          {bekleyen > 0 && (
            <Button size="sm" variant="secondary" onClick={geriDoldur} disabled={busy}>
              <Archive className="mr-1.5 h-4 w-4" />
              Eksik arşivleri üret
            </Button>
          )}
          <Button
            size="sm"
            onClick={() => dogrula(secim.length > 0 ? secim : gosterilen.map((r) => r.claim_id))}
            disabled={busy || gosterilen.length === 0}
          >
            {busy ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-1.5 h-4 w-4" />}
            {secim.length > 0 ? `${secim.length} kaydı doğrula` : "Görünenleri doğrula"}
          </Button>
        </div>
      </div>

      {/* Doğrulama ağ kullanıyor ve sayfa başına saniyeler sürüyor; kullanıcı neyi
          tetiklediğini bilerek tetiklemeli. Bu yüzden otomatik değil, düğmeye bağlı. */}
      <p className="-mt-3 text-xs text-text-tertiary">
        Doğrulama her kaydın kaynak sayfasını yeniden indirir; onlarca kayıt için dakikalar sürebilir.
      </p>

      <Tabs value={filtre} onValueChange={(v) => setFiltre(v as Filtre)}>
        {/* Beş durum filtresi dar ekrana sığmıyor: şerit kendi içinde kayar. */}
        <div className="overflow-x-auto">
          <TabsList className="w-max">
            {FILTRELER.map((f) => (
              <TabsTrigger key={f.value} value={f.value}>
                {f.label}
                {f.value !== "hepsi" && (
                  <span className="ml-1.5 tabular-nums text-text-tertiary">{sayim[f.value] ?? 0}</span>
                )}
              </TabsTrigger>
            ))}
          </TabsList>
        </div>
      </Tabs>

      {error && <ErrorState error={error} onRetry={reload} />}
      {loading && !records && <SkeletonRows count={6} />}
      {records && gosterilen.length === 0 && (
        <EmptyState
          title="Bu filtrede arşiv yok"
          description="Arşivler promote sırasında kendiliğinden oluşur. Eski claim'ler için üstteki düğmeyle geri doldurabilirsin."
        />
      )}

      <ul className="flex flex-col gap-2">
        {gosterilen.map((r) => (
          <ArchiveRow
            key={r.evidence_id}
            record={r}
            selected={secim.includes(r.claim_id)}
            onToggle={(checked) =>
              setSelected((s) => (checked ? [...s, r.claim_id] : s.filter((id) => id !== r.claim_id)))
            }
          />
        ))}
      </ul>
    </div>
  );
}

function ArchiveRow({
  record,
  selected,
  onToggle,
}: {
  record: ArchiveRecord;
  selected: boolean;
  onToggle: (checked: boolean) => void;
}) {
  const gorunum = DURUM_GORUNUMU[record.archive_status];
  const Icon = gorunum.icon;
  return (
    <li className="rounded-xl border border-border bg-surface p-4">
      <div className="flex items-start gap-3">
        <Checkbox
          checked={selected}
          onCheckedChange={(c) => onToggle(c === true)}
          aria-label={`${record.claim_headline ?? "Kayıt"} seçimi`}
        />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className={gorunum.sinif}>
              <Icon aria-hidden className="mr-1 h-3 w-3" />
              {gorunum.kisa}
            </Badge>
            {record.scored && (
              <Badge variant="outline" className="border-confidence-supported/40 text-confidence-supported-text">
                Skora giriyor
              </Badge>
            )}
            {record.claim_state && (
              <ConfidenceBadge
                state={record.claim_state}
                confidence={record.claim_confidence ?? undefined}
              />
            )}
          </div>
          <p className="mt-2 text-sm font-medium leading-snug text-foreground">
            {record.claim_headline || "(başlıksız)"}
          </p>
          <p className="mt-1 text-xs text-text-secondary">
            {record.archive_note ?? record.archive_status_label}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-text-tertiary">
            <span>{host(record.archive_url)}</span>
            {record.archive_match != null && (
              <span className="tabular-nums">eşleşme %{Math.round(record.archive_match * 100)}</span>
            )}
            {record.content_hash && (
              <span className="font-mono">sha256:{record.content_hash.slice(0, 12)}</span>
            )}
            <a
              className="inline-flex items-center gap-1 underline decoration-dotted underline-offset-2 hover:text-foreground"
              href={api.evidence.textUrl(record.evidence_id)}
              target="_blank"
              rel="noreferrer"
            >
              <FileText aria-hidden className="h-3 w-3" />
              Arşiv metni
            </a>
            {record.archive_url && (
              <a
                className="inline-flex items-center gap-1 underline decoration-dotted underline-offset-2 hover:text-foreground"
                href={record.archive_url}
                target="_blank"
                rel="noreferrer"
              >
                <ExternalLink aria-hidden className="h-3 w-3" />
                Canlı sayfa
              </a>
            )}
          </div>
        </div>
      </div>
    </li>
  );
}
