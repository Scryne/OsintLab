import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3 text-center">
      <h1 className="font-display text-[2rem] font-semibold tracking-tight text-balance text-foreground">
        Sayfa bulunamadı
      </h1>
      <p className="max-w-md text-sm text-muted-foreground">
        Bağlantı eskimiş ya da kayıt kaldırılmış olabilir. Ana Çalışma Alanı&apos;ndan devam edebilirsiniz.
      </p>
      <Link href="/" className="text-sm font-medium text-foreground underline underline-offset-4">
        Ana Çalışma Alanı&apos;na dön
      </Link>
    </div>
  );
}
