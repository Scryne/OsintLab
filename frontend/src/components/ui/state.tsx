import { AlertTriangle, Loader2, SearchX } from "lucide-react";
import { Button } from "@/components/ui/button";

export function LoadingState({ label = "Yükleniyor…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 py-8 text-sm text-text-secondary">
      <Loader2 aria-hidden className="h-4 w-4 animate-spin" />
      {label}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-start gap-2 rounded-lg border border-priority-critical/30 bg-priority-critical/5 p-4 text-sm">
      <div className="flex items-center gap-2 text-priority-critical-text">
        <AlertTriangle aria-hidden className="h-4 w-4" />
        <span className="font-medium">Bir şeyler ters gitti</span>
      </div>
      <p className="text-text-secondary">{message}</p>
      {onRetry && (
        <Button size="sm" variant="outline" onClick={onRetry}>
          Tekrar dene
        </Button>
      )}
    </div>
  );
}

export function EmptyState({ title, description }: { title: string; description?: string }) {
  return (
    <div className="flex flex-col items-start gap-1.5 rounded-lg border border-border bg-surface p-6 text-sm">
      <div className="flex items-center gap-2 text-text-secondary">
        <SearchX aria-hidden className="h-4 w-4" />
        <span className="font-medium text-foreground">{title}</span>
      </div>
      {description && <p className="text-text-tertiary">{description}</p>}
    </div>
  );
}
