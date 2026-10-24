"""Faz 34 — MEDIAINT: görsel kanıtın deterministik analizi.

Bir fotoğrafın OSINT değeri çoğu zaman pikselde değil, dosyanın kendisinde: kamera, çekim zamanı,
GPS, düzenleme yazılımı, içerik kimlik bilgisi (C2PA), üretken model izleri. Buradaki her alan
dosyadan OKUNUR, hiçbiri tahmin edilmez — "AI üretimi mi" sorusunun cevabı bir sınıflandırıcı
değil, dosyanın kendi beyanı (XMP `DigitalSourceType`, PNG metin bloğundaki üretim parametreleri).
Beyan yoksa "iz yok" denir, "gerçek" denmez: metadata silinebilir, eksikliği kanıt değildir.

Algısal hash (dHash/aHash) aynı görselin yeniden kodlanmış/küçültülmüş kopyalarını bulmak için:
SHA-256 tek bir baytta değişir, dHash değişmez.

Görseldeki metin (ekran görüntüsü, tabela, belge fotoğrafı) Tesseract ile okunur ve gözlem/seçici
hattına girer — DOCINT'in OCR'ı yalnızca PDF'i kapsıyordu.

Bu metadata da güvenilmeyen veridir (Q22): yalnızca gösterilir ve indekslenir, yorumlanmaz.
"""
from __future__ import annotations

import io
import logging
import re
from datetime import datetime
from pathlib import Path

from PIL import ExifTags, Image, ImageOps, UnidentifiedImageError

logger = logging.getLogger(__name__)

IMAGE_FORMATS = {"JPEG", "PNG", "WEBP", "TIFF", "GIF", "BMP", "HEIF", "MPO"}
MAX_PIXELS = 80_000_000

# Bir kamera dosyasında OSINT açısından anlamlı EXIF alanları. Sıra arayüzdeki sıradır.
_EXIF_FIELDS = (
    "Make", "Model", "LensMake", "LensModel", "BodySerialNumber", "Software", "Artist", "Copyright",
    "DateTimeOriginal", "DateTimeDigitized", "DateTime", "OffsetTimeOriginal",
    "ExposureTime", "FNumber", "ISOSpeedRatings", "FocalLength", "Orientation", "ImageDescription",
    "HostComputer",
)

_EDITORS = re.compile(r"\b(?:photoshop|lightroom|gimp|snapseed|picsart|canva|affinity|pixelmator|facetune|vsco|capture one|darktable)\b", re.I)
_AI_MARKERS = re.compile(
    r"\b(?:trainedAlgorithmicMedia|compositeWithTrainedAlgorithmicMedia|algorithmicMedia|midjourney|dall[·\-\s]?e|"
    r"stable diffusion|novelai|firefly|imagen|gpt-image|comfyui|automatic1111|invokeai|flux\.1|flux-dev|flux-schnell)\b",
    re.I,
)


def is_image(path: Path) -> bool:
    try:
        with Image.open(path) as img:
            return (img.format or "").upper() in IMAGE_FORMATS
    except (UnidentifiedImageError, OSError, ValueError):
        return False


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _clean(value) -> str | float | None:
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    if isinstance(value, str):
        value = value.replace("\x00", "").strip()
        return value[:500] or None
    num = _num(value)
    if num is not None:
        return round(num, 6)
    return str(value)[:200] if value is not None else None


def _dms_to_deg(dms, ref) -> float | None:
    try:
        d, m, s = (float(x) for x in dms)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    deg = d + m / 60 + s / 3600
    if str(ref).upper() in ("S", "W"):
        deg = -deg
    return round(deg, 6)


def _gps(exif) -> dict | None:
    try:
        raw = exif.get_ifd(0x8825)
    except (KeyError, AttributeError):
        return None
    if not raw:
        return None
    gps = {ExifTags.GPSTAGS.get(k, str(k)): v for k, v in raw.items()}
    lat = _dms_to_deg(gps.get("GPSLatitude"), gps.get("GPSLatitudeRef"))
    lon = _dms_to_deg(gps.get("GPSLongitude"), gps.get("GPSLongitudeRef"))
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180) or (lat == 0 and lon == 0):
        return None
    out = {"lat": lat, "lon": lon}
    alt = _num(gps.get("GPSAltitude"))
    if alt is not None:
        out["altitude_m"] = round(-alt if gps.get("GPSAltitudeRef") in (1, b"\x01") else alt, 1)
    direction = _num(gps.get("GPSImgDirection"))
    if direction is not None:
        out["direction_deg"] = round(direction, 1)
        out["direction_ref"] = _clean(gps.get("GPSImgDirectionRef"))
    stamp = gps.get("GPSTimeStamp")
    date = _clean(gps.get("GPSDateStamp"))
    if stamp and date:
        try:
            h, m, s = (int(float(x)) for x in stamp)
            out["timestamp_utc"] = f"{str(date).replace(':', '-')}T{h:02d}:{m:02d}:{s:02d}Z"
        except (TypeError, ValueError):
            pass
    return out


def dhash(img: Image.Image, size: int = 8) -> str:
    gray = ImageOps.exif_transpose(img).convert("L").resize((size + 1, size), Image.Resampling.LANCZOS)
    px = list(gray.tobytes())
    bits = 0
    for row in range(size):
        for col in range(size):
            left = px[row * (size + 1) + col]
            right = px[row * (size + 1) + col + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return f"{bits:0{size * size // 4}x}"


def ahash(img: Image.Image, size: int = 8) -> str:
    gray = ImageOps.exif_transpose(img).convert("L").resize((size, size), Image.Resampling.LANCZOS)
    px = list(gray.tobytes())
    mean = sum(px) / len(px)
    bits = 0
    for p in px:
        bits = (bits << 1) | (1 if p >= mean else 0)
    return f"{bits:0{size * size // 4}x}"


def hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def _xmp(raw: bytes) -> dict:
    start = raw.find(b"<x:xmpmeta")
    if start < 0:
        return {}
    end = raw.find(b"</x:xmpmeta>", start)
    block = raw[start:end + 12 if end > 0 else start + 200_000].decode("utf-8", errors="replace")
    out: dict = {"present": True}
    for key in ("CreatorTool", "DigitalSourceType", "History", "Credit", "Rights"):
        m = re.search(rf"{key}[=>]\s*\"?([^\"<]{{1,300}})", block)
        if m:
            out[key] = m.group(1).strip()
    return out


def analyze(path: Path) -> dict:
    raw = path.read_bytes()
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    with Image.open(io.BytesIO(raw)) as img:
        img.load()
        info = {
            "format": img.format,
            "width": img.width,
            "height": img.height,
            "mode": img.mode,
            "frames": getattr(img, "n_frames", 1),
        }
        exif = img.getexif()
        fields: dict = {}
        base = {ExifTags.TAGS.get(k, str(k)): v for k, v in exif.items()}
        try:
            base.update({ExifTags.TAGS.get(k, str(k)): v for k, v in exif.get_ifd(0x8769).items()})
        except (KeyError, AttributeError):
            pass
        for name in _EXIF_FIELDS:
            if name in base and _clean(base[name]) not in (None, ""):
                fields[name] = _clean(base[name])
        gps = _gps(exif)
        text_chunks = {}
        for key, value in (img.info or {}).items():
            if isinstance(value, (str, bytes)) and key not in ("exif", "icc_profile", "xmp", "dpi"):
                text = _clean(value)
                if isinstance(text, str):
                    text_chunks[str(key)] = text[:1500]
        hashes = {"dhash": dhash(img), "ahash": ahash(img)}

    xmp = _xmp(raw)
    c2pa = b"c2pa" in raw or b"jumb" in raw[:2_000_000]
    blob = " ".join([str(v) for v in fields.values()] + list(text_chunks.values()) + [str(v) for v in xmp.values()])
    ai = sorted({m.group(0) for m in _AI_MARKERS.finditer(blob)}, key=str.lower)
    editors = sorted({m.group(0) for m in _EDITORS.finditer(blob)}, key=str.lower)
    flags = []
    if c2pa:
        flags.append({"code": "C2PA", "text": "İçerik kimlik bilgisi (C2PA) bloğu var — contentcredentials.org/verify ile doğrulanabilir."})
    if ai:
        flags.append({"code": "AI_DECLARED", "text": f"Dosya üretken bir araç beyan ediyor: {', '.join(ai)}"})
    if editors:
        flags.append({"code": "EDITED", "text": f"Düzenleme yazılımı izi: {', '.join(editors)}"})
    if not fields and not gps and not xmp:
        flags.append({"code": "NO_METADATA", "text": "Metadata yok — sosyal medya platformları yüklemede siler; bu kendi başına bir şey kanıtlamaz."})
    if "DateTimeOriginal" in fields and "DateTime" in fields and fields["DateTimeOriginal"] != fields["DateTime"]:
        flags.append({"code": "MODIFIED_AFTER", "text": f"Çekimden sonra kaydedilmiş: çekim {fields['DateTimeOriginal']}, son kayıt {fields['DateTime']}."})

    taken = None
    if isinstance(fields.get("DateTimeOriginal"), str):
        try:
            taken = datetime.strptime(fields["DateTimeOriginal"][:19], "%Y:%m:%d %H:%M:%S").isoformat()
        except ValueError:
            pass
    return {
        "image": info,
        "exif": fields,
        "taken_local": taken,
        "gps": gps,
        "xmp": xmp,
        "text_chunks": text_chunks,
        "c2pa": c2pa,
        "hashes": hashes,
        "flags": flags,
    }


def ocr_image(path: Path, lang: str, timeout: int = 60) -> dict | None:
    """Görseldeki yazı. Tesseract kurulu değilse None — çağıran OCR'sız devam eder."""
    from app import docint

    if not docint.ocr_status()["available"]:
        return None
    import pytesseract

    docint._apply_tessdata_prefix()
    cmd = docint.tesseract_cmd()
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
        # Küçük ekran görüntüleri büyütülünce Tesseract belirgin biçimde daha iyi okuyor.
        if img.width < 1400:
            scale = 1400 / img.width
            img = img.resize((int(img.width * scale), int(img.height * scale)), Image.Resampling.LANCZOS)
        data = pytesseract.image_to_data(img, lang=lang, output_type=pytesseract.Output.DICT, timeout=timeout)
    words, confs = [], []
    for text, conf in zip(data.get("text", []), data.get("conf", []), strict=False):
        if str(text).strip():
            words.append(str(text))
            c = _num(conf)
            if c is not None and c >= 0:
                confs.append(c / 100)
    text = " ".join(words).strip()
    return {"text": text, "confidence": round(sum(confs) / len(confs), 3) if confs else None, "lang": lang}


def preview_png(path: Path, max_side: int = 1200) -> bytes:
    """Arayüz önizlemesi: Pillow'dan geçirilip PNG olarak YENİDEN kodlanır. Orijinal dosya hiçbir
    zaman tarayıcıda satır içi açılmaz (kanıt dosyaları güvenilmeyen kaynaktan geliyor); yeniden
    kodlama metadata'yı ve gömülü her şeyi atar, geriye yalnızca pikseller kalır."""
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
        img.thumbnail((max_side, max_side))
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()
