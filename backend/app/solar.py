"""Faz 34 — güneş konumu ve kronolokasyon (fotoğrafın çekildiği saati gölgeden bulmak).

NOAA'nın Güneş Konumu hesabı (Solar Calculator, Meeus'ün "Astronomical Algorithms"ına dayanır):
verilen enlem/boylam ve UTC zamanında güneşin azimutu (kuzeyden saat yönünde) ve yüksekliği.
Doğruluk ±1° mertebesinde — gölgeden saat tahmini için fazlasıyla yeterli. Bağımlılık yok, ağ yok
(pysolar GPL olduğu için bilerek eklenmedi).

Gölge: yüksekliği h olan bir nesnenin gölgesi güneşin TERSİNE düşer (azimut + 180°) ve boyu
h / tan(yükseklik). Kronolokasyon bunun tersi: ölçülen gölge yönü ve/veya boy oranı verilince
günün hangi dakikalarında bu geometri oluştuğu taranır.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone


def _julian_day(dt: datetime) -> float:
    dt = dt.astimezone(timezone.utc)
    return dt.timestamp() / 86400.0 + 2440587.5


def sun_position(lat: float, lon: float, when: datetime) -> dict:
    """{'azimuth': derece (0=K, 90=D), 'elevation': derece (atmosferik kırılma düzeltmeli)}."""
    jd = _julian_day(when)
    t = (jd - 2451545.0) / 36525.0
    l0 = (280.46646 + t * (36000.76983 + t * 0.0003032)) % 360
    m = 357.52911 + t * (35999.05029 - 0.0001537 * t)
    e = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)
    mr = math.radians(m)
    c = (math.sin(mr) * (1.914602 - t * (0.004817 + 0.000014 * t))
         + math.sin(2 * mr) * (0.019993 - 0.000101 * t) + math.sin(3 * mr) * 0.000289)
    true_long = l0 + c
    omega = 125.04 - 1934.136 * t
    app_long = true_long - 0.00569 - 0.00478 * math.sin(math.radians(omega))
    eps0 = 23 + (26 + (21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))) / 60) / 60
    eps = eps0 + 0.00256 * math.cos(math.radians(omega))
    decl = math.degrees(math.asin(math.sin(math.radians(eps)) * math.sin(math.radians(app_long))))
    y = math.tan(math.radians(eps / 2)) ** 2
    l0r = math.radians(l0)
    eq_time = 4 * math.degrees(
        y * math.sin(2 * l0r) - 2 * e * math.sin(mr) + 4 * e * y * math.sin(mr) * math.cos(2 * l0r)
        - 0.5 * y * y * math.sin(4 * l0r) - 1.25 * e * e * math.sin(2 * mr)
    )
    utc = when.astimezone(timezone.utc)
    minutes = utc.hour * 60 + utc.minute + utc.second / 60
    true_solar = (minutes + eq_time + 4 * lon) % 1440
    hour_angle = true_solar / 4 - 180
    latr, declr, har = math.radians(lat), math.radians(decl), math.radians(hour_angle)
    cos_zen = math.sin(latr) * math.sin(declr) + math.cos(latr) * math.cos(declr) * math.cos(har)
    zenith = math.degrees(math.acos(max(-1.0, min(1.0, cos_zen))))
    elevation = 90 - zenith
    # Atmosferik kırılma (NOAA yaklaşımı).
    if elevation > 85:
        refraction = 0.0
    elif elevation > 5:
        te = math.tan(math.radians(elevation))
        refraction = 58.1 / te - 0.07 / te ** 3 + 0.000086 / te ** 5
    elif elevation > -0.575:
        refraction = 1735 + elevation * (-518.2 + elevation * (103.4 + elevation * (-12.79 + elevation * 0.711)))
    else:
        refraction = -20.772 / math.tan(math.radians(elevation))
    elevation += refraction / 3600
    zr = math.radians(zenith)
    denom = math.cos(latr) * math.sin(zr)
    if abs(denom) < 1e-9:
        azimuth = 180.0
    else:
        cos_az = (math.sin(latr) * math.cos(zr) - math.sin(declr)) / denom
        az = math.degrees(math.acos(max(-1.0, min(1.0, cos_az))))
        azimuth = (az + 180) % 360 if hour_angle > 0 else (540 - az) % 360
    return {"azimuth": round(azimuth, 2), "elevation": round(elevation, 2)}


def shadow(elevation: float, azimuth: float) -> dict | None:
    """Birim yükseklikteki bir nesnenin gölgesi. Güneş ufkun altındaysa gölge yok."""
    if elevation <= 0.5:
        return None
    return {"direction": round((azimuth + 180) % 360, 1), "length_ratio": round(1 / math.tan(math.radians(elevation)), 3)}


def day_table(lat: float, lon: float, day: datetime, step_minutes: int = 15) -> dict:
    """Bir günün (UTC 00:00'dan başlayan 24 saat) güneş tablosu + doğuş/batış/öğle."""
    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    rows = []
    sunrise = sunset = noon = None
    best_elev = -99.0
    prev = None
    for i in range(0, 24 * 60 + 1, 1):
        t = start + timedelta(minutes=i)
        pos = sun_position(lat, lon, t)
        if prev is not None:
            if prev["elevation"] < -0.833 <= pos["elevation"] and sunrise is None:
                sunrise = t
            if prev["elevation"] >= -0.833 > pos["elevation"]:
                sunset = t
        if pos["elevation"] > best_elev:
            best_elev, noon = pos["elevation"], t
        if i % step_minutes == 0 and pos["elevation"] > -6:
            rows.append({"utc": t.isoformat(), **pos, "shadow": shadow(pos["elevation"], pos["azimuth"])})
        prev = pos
    return {
        "date": start.date().isoformat(),
        "sunrise_utc": sunrise.isoformat() if sunrise else None,
        "sunset_utc": sunset.isoformat() if sunset else None,
        "solar_noon_utc": noon.isoformat() if noon else None,
        "max_elevation": round(best_elev, 2),
        "rows": rows,
    }


def _angle_diff(a: float, b: float) -> float:
    return abs((a - b + 180) % 360 - 180)


def chronolocate(
    lat: float, lon: float, day: datetime, *,
    shadow_direction: float | None = None, length_ratio: float | None = None,
    direction_tolerance: float = 5.0, ratio_tolerance: float = 0.1,
) -> list[dict]:
    """Ölçülen gölge geometrisine uyan dakikalar (UTC), en iyi eşleşme önce. Birbirine bitişik
    dakikalar tek bir pencereye birleştirilir — sabah ve akşam iki ayrı aday olarak döner."""
    if shadow_direction is None and length_ratio is None:
        raise ValueError("Gölge yönü ya da boy oranından en az biri gerekli.")
    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    hits = []
    for i in range(24 * 60):
        t = start + timedelta(minutes=i)
        pos = sun_position(lat, lon, t)
        sh = shadow(pos["elevation"], pos["azimuth"])
        if sh is None:
            continue
        err = 0.0
        if shadow_direction is not None:
            d = _angle_diff(sh["direction"], shadow_direction)
            if d > direction_tolerance:
                continue
            err += d / max(direction_tolerance, 0.1)
        if length_ratio is not None:
            r = abs(sh["length_ratio"] - length_ratio) / max(length_ratio, 0.01)
            if r > ratio_tolerance:
                continue
            err += r / max(ratio_tolerance, 0.01)
        hits.append((t, err, pos, sh))
    windows: list[list] = []
    for hit in hits:
        if windows and (hit[0] - windows[-1][-1][0]) <= timedelta(minutes=1):
            windows[-1].append(hit)
        else:
            windows.append([hit])
    out = []
    for w in windows:
        best = min(w, key=lambda h: h[1])
        out.append({
            "from_utc": w[0][0].isoformat(),
            "to_utc": w[-1][0].isoformat(),
            "best_utc": best[0].isoformat(),
            "error": round(best[1], 3),
            "sun": best[2],
            "shadow": best[3],
        })
    return sorted(out, key=lambda x: x["error"])
