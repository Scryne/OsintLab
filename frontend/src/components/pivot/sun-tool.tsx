"use client";

import { useState } from "react";
import { useSearchParams } from "next/navigation";
import { Sun } from "lucide-react";
import { api } from "@/lib/api";
import type { ChronoWindow, SunResult } from "@/lib/types-pivot";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/toast";

function utcTime(iso: string | null): string {
  return iso ? iso.slice(11, 16) : "—";
}

/** Faz 34 — güneş konumu ve kronolokasyon. Hesap yerelde (NOAA algoritması, astral ile ±0,01°
 * doğrulandı); hiçbir değer dışarı gönderilmez.
 *
 * Kullanım: fotoğraftaki dik bir nesnenin gölgesinin yönünü (kuzeyden saat yönünde) ve/veya
 * gölge boyunun nesne boyuna oranını ölç; konum ve tarih verilince bu geometrinin oluştuğu saat
 * aralıkları çıkar. Bir fotoğrafın iddia edilen saatini sınamanın standart yolu. */
export function SunTool() {
  const params = useSearchParams();
  const toast = useToast();
  const initialAt = params.get("at") ?? "";
  const [lat, setLat] = useState(params.get("lat") ?? "");
  const [lon, setLon] = useState(params.get("lon") ?? "");
  const [day, setDay] = useState(initialAt ? initialAt.slice(0, 10) : new Date().toISOString().slice(0, 10));
  const [time, setTime] = useState(initialAt ? initialAt.slice(11, 16) : "12:00");
  const [dir, setDir] = useState("");
  const [ratio, setRatio] = useState("");
  const [sun, setSun] = useState<SunResult | null>(null);
  const [windows, setWindows] = useState<ChronoWindow[] | null>(null);

  const latN = Number(lat);
  const lonN = Number(lon);
  const valid = lat.trim() !== "" && lon.trim() !== "" && Number.isFinite(latN) && Number.isFinite(lonN) && Math.abs(latN) <= 90 && Math.abs(lonN) <= 180;

  async function compute() {
    try {
      setSun(await api.sun(latN, lonN, { at: `${day}T${time}:00Z`, day }));
    } catch (err) {
      toast(err instanceof Error ? err.message : "Hesaplanamadı", "error");
    }
  }

  async function locate() {
    try {
      const res = await api.chronolocate({
        lat: latN,
        lon: lonN,
        day,
        shadow_direction: dir.trim() ? Number(dir) : null,
        length_ratio: ratio.trim() ? Number(ratio) : null,
      });
      setWindows(res.windows);
    } catch (err) {
      toast(err instanceof Error ? err.message : "Hesaplanamadı", "error");
    }
  }

  const field = (id: string, label: string, value: string, set: (v: string) => void, props: React.ComponentProps<typeof Input> = {}) => (
    <div className="flex flex-col gap-1">
      <Label htmlFor={id} className="text-xs text-text-secondary">{label}</Label>
      <Input id={id} value={value} onChange={(e) => set(e.target.value)} className="h-8 font-mono text-xs" {...props} />
    </div>
  );

  return (
    <section id="gunes" className="flex scroll-mt-6 flex-col gap-3 rounded-xl border border-border bg-surface p-4">
      <h2 className="flex items-center gap-2 text-sm font-medium text-foreground">
        <Sun aria-hidden className="h-4 w-4 text-text-tertiary" />
        Güneş konumu ve kronolokasyon
      </h2>
      <p className="max-w-2xl text-xs text-pretty text-text-secondary">
        Konum ve tarih ver: güneşin o anki yönü/yüksekliği ve dik bir nesnenin gölgesi hesaplanır. Fotoğraftaki gölgenin
        yönünü ya da boy oranını girersen, o gün bu gölgenin oluştuğu saatler bulunur. Hesap yerelde yapılır. Saatler UTC.
      </p>
      <div className="grid gap-3 sm:grid-cols-4">
        {field("sun-lat", "Enlem", lat, setLat, { placeholder: "41.0082", inputMode: "decimal" })}
        {field("sun-lon", "Boylam", lon, setLon, { placeholder: "28.9784", inputMode: "decimal" })}
        {field("sun-day", "Tarih", day, setDay, { type: "date" })}
        {field("sun-time", "Saat (UTC)", time, setTime, { type: "time" })}
      </div>
      <Button size="sm" className="self-start" onClick={compute} disabled={!valid}>Güneşi hesapla</Button>
      {sun && (
        <div className="flex flex-col gap-2 rounded-md border border-border p-3 text-sm">
          <p className="text-foreground">
            Azimut <strong className="font-mono">{sun.position.azimuth.toFixed(1)}°</strong> · yükseklik{" "}
            <strong className="font-mono">{sun.position.elevation.toFixed(1)}°</strong>
            {sun.shadow ? (
              <>
                {" "}· gölge yönü <strong className="font-mono">{sun.shadow.direction.toFixed(1)}°</strong>, boy oranı{" "}
                <strong className="font-mono">{sun.shadow.length_ratio.toFixed(2)}</strong>
              </>
            ) : (
              " · güneş ufkun altında, gölge yok"
            )}
          </p>
          <p className="font-mono text-xs text-text-tertiary">
            doğuş {utcTime(sun.day.sunrise_utc)} · öğle {utcTime(sun.day.solar_noon_utc)} (en yüksek {sun.day.max_elevation}°) · batış {utcTime(sun.day.sunset_utc)} UTC
          </p>
        </div>
      )}
      <div className="grid gap-3 sm:grid-cols-3">
        {field("sun-dir", "Ölçülen gölge yönü (°, kuzeyden)", dir, setDir, { placeholder: "örn. 315", inputMode: "decimal" })}
        {field("sun-ratio", "Gölge boyu / nesne boyu", ratio, setRatio, { placeholder: "örn. 1.4", inputMode: "decimal" })}
        <div className="flex items-end">
          <Button size="sm" variant="outline" onClick={locate} disabled={!valid || (!dir.trim() && !ratio.trim())}>Saati bul</Button>
        </div>
      </div>
      {windows && windows.length === 0 && <p className="text-sm text-text-tertiary">Bu gün bu geometriyle eşleşen saat yok — yönü, oranı ya da tarihi kontrol et.</p>}
      {windows && windows.length > 0 && (
        <ul className="flex flex-col gap-1 text-sm">
          {windows.map((w) => (
            <li key={w.best_utc} className="flex flex-wrap gap-x-3 rounded-md border border-border px-3 py-1.5 font-mono text-xs">
              <span className="text-foreground">{utcTime(w.from_utc)}–{utcTime(w.to_utc)} UTC</span>
              <span className="text-text-secondary">en iyi {utcTime(w.best_utc)}</span>
              <span className="text-text-tertiary">güneş {w.sun.azimuth.toFixed(0)}° / {w.sun.elevation.toFixed(0)}° · gölge {w.shadow.direction.toFixed(0)}°, ×{w.shadow.length_ratio.toFixed(2)}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
