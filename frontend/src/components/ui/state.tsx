import { AlertTriangle, Loader2, SearchX } from "lucide-react";
import { Button } from "@/components/ui/button";

export function LoadingState({ label = "Yükleniyor…" }: { label?: string }) {
  return (
    // `role="status"` olmadan ekran okuyucu bekleyişi hiç duyurmuyordu: metin ekrana
    // sessizce giriyordu. Bölüm-içi yüklemeler için; tam sayfa bekleyişte SkeletonDetail.
    <div role="status" className="flex items-center gap-2 py-8 text-sm text-text-secondary">
      <Loader2 aria-hidden className="h-4 w-4 animate-spin" />
      {label}
    </div>
  );
}

/** Hata mesajı ne→neden→nasıl sırasını izler.
 *
 * Önceden başlık "Bir şeyler ters gitti" idi ve altında ham `error.message` duruyordu:
 * yani sadece "neden"in yarısı vardı, "ne" belirsizdi ve "nasıl" hiç yoktu. Backend
 * ayakta değilken en sık görülen hâli bir `fetch` hatasıdır ve kullanıcıya söylenmesi
 * gereken şey "sunucuya ulaşılamadı, `start.ps1` çalışıyor mu" — ham mesaj bunu söylemez.
 *
 * `title` verilmezse mesajın şeklinden çıkarılır. Suçu kullanıcıya yüklemez. */
function explain(message: string): { title: string; hint?: string } {
  const m = message.toLowerCase();
  if (m.includes("failed to fetch") || m.includes("networkerror") || m.includes("load failed")) {
    return {
      title: "Sunucuya ulaşılamadı",
      hint: "Backend çalışmıyor olabilir. start.ps1 ile başlatıp tekrar dene.",
    };
  }
  if (m.includes("404")) return { title: "Kayıt bulunamadı", hint: "Silinmiş ya da bağlantı eski olabilir." };
  if (m.includes("409")) return { title: "Bu işlem zaten yapılmış", hint: "Sayfayı tazeleyince güncel hâlini görürsün." };
  if (m.includes("500")) return { title: "Sunucu isteği tamamlayamadı", hint: "Birkaç saniye sonra tekrar dene." };
  return { title: "İstek tamamlanamadı" };
}

export function ErrorState({
  message,
  onRetry,
  title,
}: {
  message: string;
  onRetry?: () => void;
  title?: string;
}) {
  const guess = explain(message);
  return (
    <div
      role="alert"
      className="flex flex-col items-start gap-2 rounded-lg border border-priority-critical/30 bg-priority-critical/5 p-4 text-sm"
    >
      <div className="flex items-center gap-2 text-priority-critical-text">
        <AlertTriangle aria-hidden className="h-4 w-4" />
        <span className="font-medium text-balance">{title ?? guess.title}</span>
      </div>
      {guess.hint && <p className="text-pretty text-text-secondary">{guess.hint}</p>}
      {/* Ham mesaj atılmıyor — teşhis için gerekiyor, ama artık ikincil. */}
      <p className="font-mono text-xs text-text-tertiary">{message}</p>
      {onRetry && (
        <Button size="sm" variant="outline" onClick={onRetry}>
          Tekrar dene
        </Button>
      )}
    </div>
  );
}

/** Boş durum. `action` opsiyoneldir ama gerçekten bir sonraki adım varsa verilmelidir —
 * "hiçbir şey yok" demek kullanıcıyı çıkmazda bırakır; boş bir ekranın işi, oraya nasıl
 * içerik geleceğini söylemektir. Her boş duruma zorla buton koymak da doğru değil:
 * sonraki adım başka bir sayfadaysa ya da filtreyi kaldırmaksa, onu açıklamada söyle. */
export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-start gap-1.5 rounded-lg border border-border bg-surface p-6 text-sm">
      <div className="flex items-center gap-2 text-text-secondary">
        <SearchX aria-hidden className="h-4 w-4" />
        <span className="font-medium text-balance text-foreground">{title}</span>
      </div>
      {description && <p className="text-pretty text-text-tertiary">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
