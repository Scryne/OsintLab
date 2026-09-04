"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Compass,
  Database,
  Eye,
  FileCheck,
  FolderSearch,
  GitMerge,
  Inbox as InboxIcon,
  Menu,
  Radar,
  Rss,
  Users,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { IconChip } from "@/components/ui/icon-chip";
import { WireframeGlobe } from "@/components/ui/wireframe-globe";

const NAV = [
  { href: "/", label: "Ana Çalışma Alanı", icon: Compass },
  { href: "/entities", label: "Entity'ler", icon: Users },
  { href: "/sources", label: "Kaynaklar", icon: Database },
  { href: "/investigations", label: "Investigation'lar", icon: FolderSearch },
  { href: "/observations", label: "Gözlemler", icon: Eye },
  { href: "/evidence", label: "Kanıt Kasası", icon: FileCheck },
  { href: "/collectors", label: "Toplayıcılar", icon: Rss },
  { href: "/entities/same-as", label: "Olası Eşleşmeler", icon: GitMerge },
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
        // "/entities" bir prefix olarak "/entities/same-as"ı da kapsar — en uzun eşleşen
        // href'i seçerek ikisinin aynı anda aktif görünmesini engelliyoruz.
        const active =
          href === "/"
            ? pathname === "/"
            : pathname === href ||
              (pathname.startsWith(href) &&
                !NAV.some((other) => other.href !== href && other.href.startsWith(href) && pathname.startsWith(other.href)));
        return (
          <Link
            key={href}
            href={href}
            onClick={() => setMobileNavOpen(false)}
            className={cn(
              "flex items-center justify-between rounded-md px-2.5 py-2 text-sm transition-colors",
              active
                ? "bg-white/95 text-neutral-900"
                : "text-text-secondary hover:bg-white/5 hover:text-foreground"
            )}
          >
            <span className="flex items-center gap-2">
              <Icon aria-hidden className="h-4 w-4" />
              {label}
            </span>
            {href === "/inbox" && !!inboxCount && (
              <span className="rounded-full bg-priority-critical/25 px-1.5 py-0.5 text-[10px] font-semibold text-priority-critical shadow-[0_0_8px_rgba(226,58,107,0.5)]">
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
        <div className="flex items-center gap-2.5">
          <IconChip icon={Radar} size="sm" />
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

      {/* Taslağın .dashboard-sidebar tarifi: kenarlardan boşluklu, yuvarlak köşeli "yüzen"
          cam panel — kenara yapışık düz şerit değil. */}
      <aside className="glass-panel fixed inset-y-4 left-4 z-20 hidden w-64 flex-col gap-1 overflow-hidden rounded-2xl p-4 md:flex">
        <WireframeGlobe spin className="pointer-events-none absolute -bottom-14 -right-14 -z-10 h-44 w-44 text-white/5" />
        <div className="mb-5 flex items-center gap-2.5 px-1 pt-1">
          <IconChip icon={Radar} size="sm" />
          <span className="font-display text-sm font-semibold tracking-wide text-foreground">OSINT LAB</span>
        </div>
        {navList}
        <div className="relative mt-auto px-2 pb-1 text-[10px] leading-relaxed text-text-tertiary">
          Kişisel intelligence workstation — tek kullanıcılı, local-first.
        </div>
      </aside>
      {/* 296px = sidebar'ın left-4 (16px) + w-64 (256px) + 24px boşluk — Tailwind ölçeğinde
          karşılığı yok çünkü fixed sidebar'ın tam geometrisinden türetilen bir değer. */}
      <main className="min-w-0 flex-1 p-4 md:ml-[296px] md:p-6">{children}</main>
    </div>
  );
}
