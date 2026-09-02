import type { Metadata } from "next";
import { IBM_Plex_Sans, IBM_Plex_Serif, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { AppShell } from "@/components/layout/app-shell";

const plexSans = IBM_Plex_Sans({
  variable: "--font-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

const plexSerif = IBM_Plex_Serif({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["500", "600"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "OsintLab",
  description: "Kişisel intelligence workstation — OSINT Brain",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="tr"
      className={`${plexSans.variable} ${plexSerif.variable} ${jetbrainsMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
