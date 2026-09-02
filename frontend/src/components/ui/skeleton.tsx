import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-md bg-white/[0.06]", className)} />;
}

/** Liste sayfalarındaki kart yer tutucusu — spinner yerine gerçek içeriğin şeklini taklit
 * eder, algılanan yükleme hızını iyileştirir (bkz. frontend-ui-engineering skill). */
export function SkeletonCard({ className }: { className?: string }) {
  return (
    <div className={cn("flex flex-col gap-2.5 rounded-lg border border-border bg-surface p-4", className)}>
      <div className="flex items-center justify-between">
        <Skeleton className="h-4 w-2/5" />
        <Skeleton className="h-5 w-16 rounded-full" />
      </div>
      <Skeleton className="h-3 w-3/5" />
    </div>
  );
}

export function SkeletonList({ count = 3, className }: { count?: number; className?: string }) {
  return (
    <div className={cn("grid grid-cols-1 gap-2 sm:grid-cols-2", className)}>
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  );
}

/** Tek sütun satır listeleri için (Observations, Investigations, Inbox — kart değil, tam
 * genişlikte satır). */
export function SkeletonRows({ count = 4, className }: { count?: number; className?: string }) {
  return (
    <div className={cn("flex flex-col gap-2", className)}>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="flex items-center justify-between gap-3 rounded-lg border border-border bg-surface p-3">
          <Skeleton className="h-4 w-2/3" />
          <Skeleton className="h-5 w-16 shrink-0 rounded-full" />
        </div>
      ))}
    </div>
  );
}
