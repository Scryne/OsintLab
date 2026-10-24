import Link from "next/link";
import { EyeOff, Globe2, Hash, KeyRound, Link2, Mail, MapPin, Network, ShieldAlert, Swords, Wallet } from "lucide-react";
import { cn } from "@/lib/utils";
import { KIND_LABELS, selectorHref, type SelectorKind } from "@/lib/types-pivot";

export const KIND_ICON: Record<SelectorKind, typeof Globe2> = {
  domain: Globe2,
  ip: Network,
  url: Link2,
  email: Mail,
  md5: Hash,
  sha1: Hash,
  sha256: Hash,
  cve: ShieldAlert,
  attack: Swords,
  asn: Network,
  btc: Wallet,
  eth: Wallet,
  coord: MapPin,
};

/** Seçici değeri her zaman mono yazılır (DESIGN.md: mono = "bu bir kayıt, insan cümlesi değil").
 * Tür bir renkle DEĞİL ikon + kısa etiketle ayrılır: confidence ve priority dışında üçüncü bir
 * renk ailesi açmak ikisini de sulandırırdı. */
export function SelectorChip({
  id,
  kind,
  value,
  link = true,
  ignored,
  className,
}: {
  id: string;
  kind: SelectorKind;
  value: string;
  link?: boolean;
  ignored?: boolean;
  className?: string;
}) {
  const Icon = ignored ? EyeOff : (KIND_ICON[kind] ?? KeyRound);
  const body = (
    <>
      <Icon aria-hidden className="h-3.5 w-3.5 shrink-0 text-text-tertiary" />
      <span className="shrink-0 text-[10px] font-medium uppercase tracking-wide text-text-tertiary">{KIND_LABELS[kind]}</span>
      <span className={cn("min-w-0 truncate font-mono text-xs text-foreground", ignored && "line-through decoration-white/30")}>{value}</span>
    </>
  );
  const cls = cn(
    "inline-flex max-w-full min-w-0 items-center gap-1.5 rounded-md border border-border bg-surface px-2 py-1",
    link && "transition-colors hover:border-white/25 hover:bg-white/[0.07]",
    className
  );
  return link ? (
    <Link href={selectorHref(id)} className={cls} title={value}>
      {body}
    </Link>
  ) : (
    <span className={cls} title={value}>
      {body}
    </span>
  );
}
