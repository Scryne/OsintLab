"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Compass, FolderSearch, Inbox as InboxIcon, Menu, Radar, Users, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";

const NAV = [
  { href: "/", label: "Ana Çalışma Alanı", icon: Compass },
  { href: "/entities", label: "Entity'ler", icon: Users },
  { href: "/investigations", label: "Investigation'lar", icon: FolderSearch },
  { href: "/inbox", label: "Inbox", icon: InboxIcon },
] as const;

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [inboxCount, setInboxCount] = useState<number | null>(null);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.inbox
      .list({ status: "NEW" })
      .then((items) => {
        if (!cancelled) setInboxCount(items.length);
      })
      .catch(() => {
        if (!cancelled) setInboxCount(null);
      });
    return () => {
      cancelled = true;
    };
  }, [pathname]);

  const navList = (
    <nav className="flex flex-col gap-1">
      {NAV.map(({ href, label, icon: Icon }) => {
        const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            onClick={() => setMobileNavOpen(false)}
            className={cn(
              "flex items-center justify-between rounded-md px-2.5 py-2 text-sm transition-colors",
              active
                ? "bg-brand-accent/15 text-foreground"
                : "text-text-secondary hover:bg-white/5 hover:text-foreground"
            )}
          >
            <span className="flex items-center gap-2">
              <Icon aria-hidden className="h-4 w-4" />
              {label}
            </span>
            {href === "/inbox" && !!inboxCount && (
              <span className="rounded-full bg-priority-critical/20 px-1.5 py-0.5 text-[10px] font-semibold text-priority-critical">
                {inboxCount}
              </span>
            )}
          </Link>
        );
      })}
    </nav>
  );

  return (
    <div className="flex min-h-screen w-full flex-col md:flex-row">
      {/* Mobil üst bar — sidebar 768px altında gizli, hamburger ile açılıyor. */}
      <div className="glass-panel sticky top-0 z-30 flex items-center justify-between p-3 md:hidden">
        <div className="flex items-center gap-2">
          <Radar aria-hidden className="h-5 w-5 text-brand-accent" />
          <span className="font-display text-sm font-semibold tracking-wide text-foreground">OSINT LAB</span>
        </div>
        <button
          type="button"
          aria-label={mobileNavOpen ? "Menüyü kapat" : "Menüyü aç"}
          aria-expanded={mobileNavOpen}
          onClick={() => setMobileNavOpen((o) => !o)}
          className="rounded-md p-2 text-foreground hover:bg-white/5"
        >
          {mobileNavOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>
      {mobileNavOpen && (
        <div className="glass-panel sticky top-[57px] z-30 p-3 md:hidden">{navList}</div>
      )}

      <aside className="glass-panel sticky top-0 z-20 hidden h-screen w-56 shrink-0 flex-col gap-1 p-3 md:flex">
        <div className="mb-4 flex items-center gap-2 px-2 pt-1">
          <Radar aria-hidden className="h-5 w-5 text-brand-accent" />
          <span className="font-display text-sm font-semibold tracking-wide text-foreground">OSINT LAB</span>
        </div>
        {navList}
        <div className="mt-auto px-2 pb-1 text-[10px] leading-relaxed text-text-tertiary">
          Kişisel intelligence workstation — tek kullanıcılı, local-first.
        </div>
      </aside>
      <main className="min-w-0 flex-1 p-4 md:p-6">{children}</main>
    </div>
  );
}
