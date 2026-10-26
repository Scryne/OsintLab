"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  Archive,
  CalendarClock,
  Compass,
  Crosshair,
  FlaskConical,
  Database,
  Eye,
  FileCheck,
  FolderSearch,
  GitMerge,
  Inbox as InboxIcon,
  Link2,
  ListChecks,
  Menu,
  Network,
  Radar,
  Rss,
  Share2,
  UserPlus,
  Users,
  Waypoints,
  Wrench,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { IconChip } from "@/components/ui/icon-chip";
import { WireframeGlobe } from "@/components/ui/wireframe-globe";
import { PageHelpButton } from "@/components/layout/page-help-button";
import { CommandPalette, CommandPaletteHint } from "@/components/layout/command-palette";

const NAV = [
  { href: "/", label: "Ana Çalışma Alanı", icon: Compass },
  { href: "/entities", label: "Entity'ler", icon: Users },
  // Faz 18: event katmanı Faz 1'den beri şemada vardı ve arayüzden ERİŞİLEMİYORDU — nav'da
  // girişi, listesi, oluşturma formu yoktu. Grafta sıfır event olmasının sebebi buydu.
  { href: "/events", label: "Olaylar", icon: CalendarClock },
  // Faz 29-32: seçiciler (CVE, alan adı, IP, hash...) ve onların zenginleştirilmesi. Entity'lerin
  // hemen altında, çünkü ikisi aynı soruyu iki düzeyde soruyor: "kim" ve "hangi altyapı/gösterge".
  { href: "/selectors", label: "Seçiciler", icon: Crosshair },
  { href: "/enrichment", label: "Zenginleştirme", icon: FlaskConical },
  { href: "/tools", label: "Araç Rehberi", icon: Wrench },
  { href: "/sources", label: "Kaynaklar", icon: Database },
  { href: "/investigations", label: "Investigation'lar", icon: FolderSearch },
  { href: "/observations", label: "Gözlemler", icon: Eye },
  // Faz 16: kuyruk kendi nav satırında, çünkü rozet olmadan "kaç gözlem bekliyor" sorusunun
  // cevabı hiçbir yerde görünmüyordu — 221 rakamı ancak API'ye elle sorulunca çıkmıştı.
  { href: "/observations/queue", label: "Promote Kuyruğu", icon: ListChecks },
  // Faz 17: kuyruğun claim tarafındaki karşılığı — gözlem bilgiye dönüştükten sonra
  // bilginin güvenilirlik kazandığı adım.
  { href: "/corroboration", label: "Doğrulama", icon: Link2 },
  { href: "/evidence", label: "Kanıt Kasası", icon: FileCheck },
  // Faz 26: arşiv kasadan AYRI bir satır. Kasa kullanıcının kendi yüklediği kanıtın yeri;
  // arşiv her promote'ta kendiliğinden oluşan bir provenance kaydı. Aynı listeye konsalardı
  // 3 belgelik kasa bir gecede 58 satır olur, elle yüklenen kanıt kendi kasasında kaybolurdu.
  { href: "/archive", label: "Kaynak Arşivi", icon: Archive },
  { href: "/collectors", label: "Toplayıcılar", icon: Rss },
  // Faz 20: entity'ler bugüne kadar yalnızca ELLE yaratıldı (5 tane); claim metinlerindeki
  // düzinelerce ad hiçbir yerde önerilmiyordu.
  { href: "/entities/candidates", label: "Entity Adayları", icon: UserPlus },
  // Faz 21: entity sayısı 58'e çıktı ama 53'ü izole kaldı — bir claim yalnızca TEK bir şey
  // "hakkında" olabildiği için ölçülen 134 değmenin 129'u graf'a giremiyordu.
  { href: "/claims/mentions", label: "Bağ Adayları", icon: Waypoints },
  // Faz 22: 109 aday çifte karşılık graf'ta 1 kenar vardı; adayları tek tek entity
  // sayfalarında gezmek kararı pahalı yapan şeyin ta kendisiydi.
  { href: "/entities/relations", label: "İlişki Adayları", icon: Share2 },
  // Faz 22: Faz 8'in "Entity Graph paneli duruyor" notunun yanlış olduğu 2026-09-02'de
  // bulunmuş ve o günden beri kapanmamıştı.
  { href: "/graph", label: "Graf", icon: Network },
  { href: "/entities/same-as", label: "Olası Eşleşmeler", icon: GitMerge },
  { href: "/inbox", label: "Inbox", icon: InboxIcon },
] as const;

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  // Rozet de canlı: sayfa değişimini beklemek, "arkada bir şey düştü mü" sorusunu ancak
  // kullanıcı gezinirse cevaplardı — oysa Inbox'a bakmayı hatırlatan şey tam da bu rozet.
  const { data: newItems } = useApi(() => api.inbox.list({ status: "NEW" }), [pathname], {
    pollMs: 30_000,
  });
  const inboxCount = newItems?.length ?? null;
  // Kuyruk derinliği de canlı: biriken gözlem, kullanıcı o sayfaya gitmeyi akıl edene kadar
  // görünmezse Faz 16'dan önceki duruma geri dönerdi. Ayrı sayaç ucu: `/queue?limit=1` bile her
  // bekleyen gözlemi puanlıyordu ve otomatik tarama sürerken önbellek her soruda düşüyordu.
  const { data: queue } = useApi(() => api.observations.queueCount(), [pathname], {
    pollMs: 60_000,
  });
  const queueCount = queue?.pending ?? null;

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
              <span className="rounded-full bg-priority-critical/25 px-1.5 py-0.5 text-[10px] font-semibold text-priority-critical-text shadow-[0_0_8px_rgba(226,58,107,0.5)]">
                {inboxCount}
              </span>
            )}
            {/* Kuyruk rozeti bilinçli olarak alarm renginde DEĞİL: bekleyen gözlem bir
                arıza değil, normal bir iş yükü. Inbox'ın kırmızısıyla aynı olsaydı ikisi de
                anlamını yitirirdi. */}
            {href === "/observations/queue" && !!queueCount && (
              <span className="rounded-full bg-white/10 px-1.5 py-0.5 text-[10px] font-semibold tabular-nums text-text-secondary">
                {queueCount}
              </span>
            )}
          </Link>
        );
      })}
    </nav>
  );

  return (
    <div className="flex min-h-dvh w-full flex-col md:flex-row">
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
        <div className="glass-panel sticky top-[57px] z-30 p-3 md:hidden">
          <CommandPaletteHint />
          {navList}
        </div>
      )}

      {/* Taslağın .dashboard-sidebar tarifi: kenarlardan boşluklu, yuvarlak köşeli "yüzen"
          cam panel — kenara yapışık düz şerit değil. */}
      <aside className="glass-panel fixed inset-y-4 left-4 z-20 hidden w-64 flex-col gap-1 overflow-hidden rounded-2xl p-4 md:flex">
        <WireframeGlobe spin className="pointer-events-none absolute -bottom-14 -right-14 -z-10 h-44 w-44 text-white/5" />
        <div className="mb-5 flex items-center gap-2.5 px-1 pt-1">
          <IconChip icon={Radar} size="sm" />
          <span className="font-display text-sm font-semibold tracking-wide text-foreground">OSINT LAB</span>
        </div>
        {/* Nav KENDİ İÇİNDE kayıyor, panelin tamamı değil. Sidebar `fixed inset-y-4` ile
            ekran yüksekliğine kilitli ve `overflow-hidden` (yuvarlak köşe + globe kırpması
            buna bağlı); 16 nav satırı kısa ekranlarda taşınca alttakilere ULAŞILAMIYORDU —
            kaydırma yoktu, satırlar sessizce kesiliyordu. Logo ve alttaki not sabit kalsın
            diye kaydırma yalnızca bu sarmalayıcıda: aksi halde "burası neresi" bilgisi
            listeyle birlikte kayıp giderdi.
            `overscroll-contain`: nav'ın sonuna gelince kaydırma arkadaki sayfaya ATLAMASIN. */}
        <CommandPaletteHint />
        <div className="relative -mr-1 min-h-0 flex-1 overflow-y-auto overscroll-contain pr-1">
          {navList}
        </div>
        <div className="relative mt-auto px-2 pb-1 pt-3 text-[10px] leading-relaxed text-text-tertiary">
          Kişisel intelligence workstation — tek kullanıcılı, local-first.
        </div>
      </aside>
      {/* 296px = sidebar'ın left-4 (16px) + w-64 (256px) + 24px boşluk — Tailwind ölçeğinde
          karşılığı yok çünkü fixed sidebar'ın tam geometrisinden türetilen bir değer. */}
      <main className="min-w-0 flex-1 p-4 md:ml-[296px] md:p-6">
        {/* Sayfa rehberi tek bir yerden bağlanıyor: içerik pathname'den seçiliyor
            (lib/page-help.ts). 17 sayfaya ayrı ayrı düğme koymak, metnin bir kısmının
            zamanla güncellenmeden kalmasının en kolay yoluydu. */}
        <PageHelpButton />
        <CommandPalette />
        {children}
      </main>
    </div>
  );
}
