import { cn } from "@/lib/utils";

/**
 * Nötr ikon kabı — koyu, düz gri, beyaza yakın ikon (referans: sade dashboard görseli,
 * 2026-09-02 geri bildirimi). Bilerek brand-accent tintli DEĞİL: Confidence/Priority renk
 * sistemleri bu projenin TEK anlamlı renk kodlaması, chrome elementleri renkli olursa o
 * kodlama gürültüye karışır — dekorasyon nötr, bilgi hep confidence/priority.
 */
export function IconChip({
  icon: Icon,
  size = "md",
  className,
}: {
  icon: React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const sizes = {
    sm: "h-7 w-7 rounded-md",
    md: "h-9 w-9 rounded-md",
    lg: "h-11 w-11 rounded-xl",
  };
  const iconSizes = { sm: "h-3.5 w-3.5", md: "h-4 w-4", lg: "h-5 w-5" };
  return (
    <span
      className={cn(
        "glass-ring flex shrink-0 items-center justify-center bg-white/[0.06] text-text-secondary",
        sizes[size],
        className
      )}
    >
      <Icon aria-hidden className={iconSizes[size]} />
    </span>
  );
}
