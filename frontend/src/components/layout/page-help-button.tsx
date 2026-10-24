"use client";

import { usePathname } from "next/navigation";
import { HelpCircle } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { helpFor } from "@/lib/page-help";

/**
 * Sayfa rehberi düğmesi — her sayfanın sağ üstünde.
 *
 * `AppShell`e TEK bir yerden bağlanıyor, 17 sayfaya ayrı ayrı değil: içerik pathname'den
 * seçiliyor (bkz. `lib/page-help.ts`). Yeni bir sayfa eklendiğinde tek yapılacak şey o
 * dosyaya bir giriş yazmak; sayfanın kendisine dokunulmuyor.
 *
 * Rehberi olmayan bir yolda düğme HİÇ render edilmiyor — boş bir yardım penceresi, yardım
 * olmadığını anlamanın en pahalı yoludur.
 */
export function PageHelpButton() {
  const pathname = usePathname();
  const help = helpFor(pathname);
  if (!help) return null;

  return (
    <Dialog>
      <DialogTrigger
        aria-label={`${help.title} — bu sayfa nasıl kullanılır`}
        title="Bu sayfa nasıl kullanılır"
        className="glass-panel fixed right-4 top-[68px] z-30 flex h-9 w-9 items-center justify-center rounded-full text-text-secondary transition-colors hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring md:right-6 md:top-6"
      >
        <HelpCircle aria-hidden className="h-[18px] w-[18px]" />
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{help.title} — nasıl kullanılır</DialogTitle>
          <DialogDescription>
            Bu ekranda hangi işin hangi sırayla yapıldığı ve nelere dikkat edilmesi gerektiği.
          </DialogDescription>
        </DialogHeader>

        <div className="flex max-h-[60vh] flex-col gap-4 overflow-y-auto pr-1">
          <ol className="flex list-none flex-col gap-2.5">
            {help.steps.map((step, i) => (
              <li key={step} className="flex gap-2.5 text-sm leading-relaxed text-text-secondary">
                <span className="mt-px flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-white/10 text-[11px] font-semibold tabular-nums text-foreground">
                  {i + 1}
                </span>
                <span className="text-pretty">{step}</span>
              </li>
            ))}
          </ol>

          {help.warnings && help.warnings.length > 0 && (
            <div className="rounded-lg border border-priority-high/30 bg-priority-high/5 p-3">
              <p className="text-[11px] font-medium uppercase tracking-wide text-priority-high-text">
                Dikkat
              </p>
              <ul className="mt-1.5 flex flex-col gap-2">
                {help.warnings.map((w) => (
                  <li key={w} className="text-pretty text-sm leading-relaxed text-text-secondary">
                    {w}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
