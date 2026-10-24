"""Faz 29 — Seçici (selector) katmanı: metinden makine-okunur göstergelerin deterministik çıkarımı.

Entity katmanı "kim/ne hakkında" sorusunu taşıyor (kişi, kurum); bu katman ise profesyonel OSINT
pratiğinin pivot noktalarını taşıyor: alan adı, IP, URL, e-posta, dosya hash'i, CVE, ATT&CK
tekniği, ASN, kripto adresi. Ölçüldü (2026-10-24): 4.408 gözlemde 1.365 CVE geçişi (386 farklı)
ve 38 ATT&CK tekniği vardı, sistem hiçbirini tanımıyordu.

Bilinçli kararlar:

- **Kişi seçicisi yok.** Kullanıcı adı, telefon, ad-soyad çıkarılmaz — kalıcı kapsam dışı
  (hedef bazlı gözetim). E-posta yalnızca güvenlik advisory'lerinde geçen kurumsal iletişim
  adresleri için var ve zenginleştirmesi alan adı düzeyinde kalır (Faz 30).
- **Yanlış pozitif ölçülüp elendi, tahmin edilmedi.** Gerçek veride IPv4 kalıbına uyan 17 farklı
  dizinin 17'si de sürüm numarasıydı ("firmware: <=4.9.86.0", "Bootloader_2.0.6.1",
  "versions 25.1.1.1"). Kurallar bu örneklerden çıkarıldı (bkz. `_ipv4_is_version`). Defang'li
  yazım (`1.2.3[.]4`) ise yazarın bilinçli "bu bir gösterge" işaretidir ve filtreyi atlar.
- **Alan adında TLD beyaz listesi.** Dosya adları (`config.yaml`, `Node.js`) ile alan adlarını
  ayırmanın tek deterministik yolu bu. Dosya uzantısıyla çakışan ülke kodları (`.md`, `.py`,
  `.sh`, `.zip`...) yalnızca URL içinde ya da defang'li yazıldığında kabul edilir.
- **Kripto adresinde sağlama toplamı doğrulanır.** Base58 kalıbı rastgele belirteçlerle
  çakışır; base58check / bech32 doğrulaması bunu sıfıra indirir.

Toplanan metin güvenilmeyen veridir (Q22): burada yalnızca kalıp aranır, hiçbir içerik
yorumlanmaz ya da çalıştırılmaz.
"""
from __future__ import annotations

import hashlib
import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

KINDS = (
    "domain", "ip", "url", "email", "md5", "sha1", "sha256",
    "cve", "attack", "asn", "btc", "eth", "coord",
)

# Arayüzde ve raporlarda kullanılan Türkçe etiketler.
KIND_LABELS = {
    "domain": "Alan adı",
    "ip": "IP adresi",
    "url": "URL",
    "email": "E-posta",
    "md5": "MD5",
    "sha1": "SHA-1",
    "sha256": "SHA-256",
    "cve": "CVE",
    "attack": "ATT&CK tekniği",
    "asn": "ASN",
    "btc": "Bitcoin adresi",
    "eth": "Ethereum adresi",
    "coord": "Koordinat",
}

CONTEXT_RADIUS = 70

# --- Refang -----------------------------------------------------------------
#
# Tehdit istihbaratı metinleri göstergeleri tıklanamaz hale getirmek için "defang" eder:
# `hxxp://evil[.]com`, `1.2.3[.]4`, `user[@]domain[.]com`. Çıkarmadan önce geri çevrilir;
# defang'li bir eşleşme ayrıca "yazar bunu bilerek gösterge olarak yazdı" işareti taşır.
_REFANG_RULES = [
    (re.compile(r"\[\s*\.\s*\]|\(\s*\.\s*\)|\{\s*\.\s*\}|\[dot\]|\(dot\)", re.I), "."),
    (re.compile(r"\[\s*@\s*\]|\(\s*@\s*\)|\[at\]|\(at\)", re.I), "@"),
    (re.compile(r"\[\s*:\s*\]"), ":"),
    (re.compile(r"\[\s*/\s*\]"), "/"),
    (re.compile(r"\bhxxp(s?)", re.I), r"http\1"),
    (re.compile(r"\bh\*\*p(s?)", re.I), r"http\1"),
    (re.compile(r"\bfxp\b", re.I), "ftp"),
]
_DEFANG_MARK = re.compile(r"\[\s*[.@:/]\s*\]|\(\s*\.\s*\)|\[dot\]|\[at\]|hxxp|h\*\*p", re.I)


def refang(text: str) -> str:
    for pattern, repl in _REFANG_RULES:
        text = pattern.sub(repl, text)
    return text


# --- TLD listesi --------------------------------------------------------------
#
# Tam Public Suffix List bir bağımlılık ya da ağ isteği gerektirirdi; burada amaç bir alan
# adını DOĞRULAMAK değil, metindeki bir dizinin alan adı olup olmadığına karar vermek. Bütün
# iki harfli ülke kodları + yaygın jenerik TLD'ler bu karar için yeterli.
_GENERIC_TLDS = frozenset("""
com net org edu gov mil int info biz name pro aero coop museum mobi asia tel travel jobs cat
xxx post app dev page io ai co me tv cloud online site tech store blog shop news live digital
media agency network systems solutions services software security tools team group global
world today center company email club space website link click top xyz icu vip win bid loan
work fun art design studio academy finance capital bank money law legal health care clinic
energy social community foundation institute education school university science research
technology engineering consulting events events games game video audio photo pictures pics
moe one ink wiki codes zone support help guide expert host hosting domains server direct
ltd llc inc gmbh srl sarl plus mba rocks ninja guru tips tools cyber army navy airforce
google microsoft amazon apple android youtube gmail windows azure aws
berlin london paris tokyo nyc istanbul amsterdam
onion
""".split())

# Dosya uzantısıyla çakışan ülke kodları ve jenerik TLD'ler. Düz metinde `README.md`,
# `setup.py`, `install.sh`, `archive.zip` alan adı sayılmaz; yalnızca URL içinde ya da
# defang'li yazıldığında kabul edilir.
_AMBIGUOUS_TLDS = frozenset({
    "md", "py", "sh", "pl", "rs", "so", "cs", "ps", "am", "zip", "mov", "sc", "ms", "mp", "gz",
    "do", "is", "it", "in", "at", "to", "as", "be", "by", "me", "no", "my", "us", "go",
})

# Gerçek ülke kodları. "Her iki harf" kuralı ilk denemede `node.js`, `css.js` gibi dosya
# adlarını alan adı saydı (`.js` bir ülke kodu değil).
_COUNTRY_TLDS = frozenset("""
ac ad ae af ag ai al am ao aq ar as at au aw ax az ba bb bd be bf bg bh bi bj bm bn bo br bs bt
bw by bz ca cc cd cf cg ch ci ck cl cm cn co cr cu cv cw cx cy cz de dj dk dm do dz ec ee eg er
es et eu fi fj fk fm fo fr ga gd ge gf gg gh gi gl gm gn gp gq gr gs gt gu gw gy hk hm hn hr ht
hu id ie il im in io iq ir is it je jm jo jp ke kg kh ki km kn kp kr kw ky kz la lb lc li lk lr
ls lt lu lv ly ma mc md me mg mh mk ml mm mn mo mp mq mr ms mt mu mv mw mx my mz na nc ne nf ng
ni nl no np nr nu nz om pa pe pf pg ph pk pl pm pn pr ps pt pw py qa re ro rs ru rw sa sb sc sd
se sg sh si sk sl sm sn so sr ss st su sv sx sy sz tc td tf tg th tj tk tl tm tn to tr tt tv tw
tz ua ug uk us uy uz va vc ve vg vi vn vu wf ws ye yt za zm zw
""".split())


def _tld_ok(tld: str, *, strict: bool) -> bool:
    tld = tld.lower()
    if tld.startswith("xn--"):
        return True
    known = tld in _GENERIC_TLDS or tld in _COUNTRY_TLDS
    if not known:
        return False
    if strict and tld in _AMBIGUOUS_TLDS:
        return False
    return True


_LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
_DOMAIN_RE = re.compile(
    rf"(?<![\w@.\-/])((?:{_LABEL}\.)+(?:[a-z]{{2,24}}|xn--[a-z0-9-]{{2,59}}))(?![\w\-]|\.[a-z0-9])",
    re.I,
)


def normalize_domain(value: str) -> str:
    return value.strip().strip(".").lower()


def valid_domain(value: str, *, strict: bool = False) -> bool:
    """`strict`: düz metinden çıkarılırken (dosya uzantısıyla çakışan TLD'ler reddedilir)."""
    value = normalize_domain(value)
    if len(value) > 253 or "." not in value:
        return False
    labels = value.split(".")
    if any(not label or len(label) > 63 for label in labels):
        return False
    if not re.fullmatch(rf"(?:{_LABEL}\.)+[a-z0-9-]+", value):
        return False
    tld = labels[-1]
    if tld.isdigit():
        return False
    # Beyaz liste yalnızca DÜZ METİNDEN çıkarırken: orada "bu dizi alan adı mı" kararı veriliyor.
    # Elle girilen bir değer, bir URL'in host'u ya da bir DNS yanıtındaki ad zaten alan adıdır;
    # listede olmayan yeni bir gTLD (`.lol`, `.example`) reddedilmemeli.
    if strict and not _tld_ok(tld, strict=True):
        return False
    if not strict and (len(tld) < 2 or not (tld.isalpha() or tld.startswith("xn--"))):
        return False
    sld = labels[-2]
    # "U.S", "e.g" gibi tek harfli ikinci seviye + ülke kodu kısaltmadır; `x.com` gibi tek
    # harfli gerçek alan adları jenerik TLD'lerde yaşar.
    if len(sld) == 1 and tld not in _GENERIC_TLDS:
        return False
    # Yalnızca rakamlardan oluşan bir ikinci seviye (sürüm numarası artığı) alan adı değildir.
    if all(label.isdigit() for label in labels[:-1]):
        return False
    return True


# --- IP ---------------------------------------------------------------------

_IPV4_RE = re.compile(r"(?<![\w.])((?:\d{1,3}\.){3}\d{1,3})(?![\w.]|\.\d)")
_IPV4_DEFANGED_RE = re.compile(
    r"(?<![\w.])(\d{1,3}(?:\s*(?:\[\.\]|\(\.\)|\[dot\]|\.)\s*\d{1,3}){3})(?![\w.])", re.I
)

# Gerçek veriden (2026-10-24, 17 örnek, 17'si sürüm numarası) çıkarılan sürüm bağlamları.
_VERSION_CONTEXT = re.compile(
    r"(?:version|versions|vers|ver|firmware|release|build|bootloader|update|upgrade|"
    r"series|section|patch|fixed in|prior|before|through|v)\s*[:=]?\s*[<>=|]*\s*$",
    re.I,
)


_VERSION_WORDS = re.compile(r"\b(?:version|versions|firmware|release|build|bootloader|patch)\b", re.I)
_VERSION_AFTER = re.compile(r"^\s*(?:and|or)\s+(?:prior|later|earlier|newer|above|below|before)", re.I)


# ">=3.2.0.0|<3.2.4.1, 3.2.4.1" — karşılaştırma işaretli bir sürüm aynı satırda hemen gerideyse
# arkasından gelen düz dörtlü sayı da o listenin parçasıdır.
_VERSION_RANGE = re.compile(r"[<>=]\s*\d+(?:\.\d+)+")


def _ipv4_is_version(text: str, start: int, end: int) -> bool:
    before = text[max(0, start - 30):start]
    after = text[end:end + 20]
    if before.endswith(("_", "-", "v", "V")) or (after[:1].isalpha() or after[:1] == "_"):
        return True
    if re.search(r"[<>=|]\s*$", before) or _VERSION_AFTER.match(after):
        return True
    line = before.splitlines()[-1] if before.splitlines() else before
    if _VERSION_CONTEXT.search(line) or _VERSION_RANGE.search(line):
        return True
    # Sürüm listesi: "versions 25.1.1.1 and prior, 25.1.2.2 and prior" — aynı satırda biraz
    # geride bir sürüm kelimesi varsa düz yazılmış dörtlü sayı IP değildir.
    wide = text[max(0, start - 90):start]
    wide_line = wide.splitlines()[-1] if wide.splitlines() else wide
    return bool(_VERSION_WORDS.search(wide_line))


def valid_public_ip(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False
    return ip.is_global and not ip.is_multicast


# --- Kripto adresleri: sağlama toplamı ---------------------------------------

_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _base58check_ok(value: str) -> bool:
    num = 0
    for char in value:
        idx = _B58.find(char)
        if idx < 0:
            return False
        num = num * 58 + idx
    raw = num.to_bytes(25, "big") if num.bit_length() <= 200 else b""
    if len(raw) != 25:
        return False
    payload, checksum = raw[:-4], raw[-4:]
    return hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4] == checksum


_BECH32 = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"


def _bech32_ok(value: str) -> bool:
    value = value.lower()
    pos = value.rfind("1")
    if pos < 1 or pos + 7 > len(value):
        return False
    hrp, data = value[:pos], value[pos + 1:]
    if any(c not in _BECH32 for c in data):
        return False
    values = [ord(c) >> 5 for c in hrp] + [0] + [ord(c) & 31 for c in hrp] + [_BECH32.find(c) for c in data]
    gen = [0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3]
    chk = 1
    for v in values:
        top = chk >> 25
        chk = (chk & 0x1FFFFFF) << 5 ^ v
        for i in range(5):
            chk ^= gen[i] if ((top >> i) & 1) else 0
    return chk in (1, 0x2BC830A3)  # bech32 / bech32m


# --- Kalıplar -------------------------------------------------------------------

_EMAIL_RE = re.compile(r"(?<![\w.+-])([a-z0-9][a-z0-9._%+-]{0,63})@((?:" + _LABEL + r"\.)+[a-z]{2,24})\b", re.I)
_CVE_RE = re.compile(r"\bCVE-(\d{4})-(\d{4,7})\b", re.I)
_ATTACK_RE = re.compile(r"\b(T1[0-6]\d{2}(?:\.\d{3})?)\b")
_ASN_RE = re.compile(r"\bASN?\s?(\d{2,10})\b")
_ETH_RE = re.compile(r"\b(0x[a-fA-F0-9]{40})\b")
_BTC_B58_RE = re.compile(r"(?<![A-Za-z0-9])([13][1-9A-HJ-NP-Za-km-z]{25,34})(?![A-Za-z0-9])")
_BTC_BECH_RE = re.compile(r"\b(bc1[ac-hj-np-z02-9]{11,71})\b", re.I)
_HASH_RE = re.compile(r"(?<![0-9a-fA-Fx])([0-9a-fA-F]{64}|[0-9a-fA-F]{40}|[0-9a-fA-F]{32})(?![0-9a-fA-F])")
_COORD_RE = re.compile(r"^\s*(-?\d{1,2}(?:\.\d+)?)\s*[,;\s]\s*(-?\d{1,3}(?:\.\d+)?)\s*$")

_SEP = r"(?:\.|\[\.\]|\(\.\)|\[dot\])"
_DEFANGED_DOMAIN_RE = re.compile(
    rf"(?<![\w@.\-/\[])((?:{_LABEL}{_SEP})+[a-z]{{2,24}})(?![\w\-\[]|\.[a-z0-9])", re.I
)

_HASH_KIND = {32: "md5", 40: "sha1", 64: "sha256"}
_URL_TRAILING = ".,;:!?)'\"»”’>"


def _strip_url(url: str) -> str:
    url = url.rstrip(_URL_TRAILING)
    # Parantez içinde verilmiş bağlantı: açılmamış bir kapanış parantezi URL'e ait değildir.
    while url.endswith(")") and url.count("(") < url.count(")"):
        url = url[:-1]
    return url


def normalize_url(url: str) -> str | None:
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return None
    if parts.scheme.lower() not in ("http", "https", "ftp") or not parts.hostname:
        return None
    host = parts.hostname.lower()
    netloc = host if parts.port is None else f"{host}:{parts.port}"
    path = parts.path or "/"
    return urlunsplit((parts.scheme.lower(), netloc, path, parts.query, ""))


@dataclass(frozen=True)
class Found:
    kind: str
    value: str
    start: int
    end: int
    defanged: bool = False

    @property
    def id(self) -> str:
        return selector_id(self.kind, self.value)


def selector_id(kind: str, value: str) -> str:
    return f"{kind}:{value}"


def _context(text: str, start: int, end: int) -> str:
    snippet = text[max(0, start - CONTEXT_RADIUS):end + CONTEXT_RADIUS]
    return " ".join(snippet.split())


def extract(text: str) -> list[Found]:
    """Metindeki tüm seçiciler, metindeki sırasıyla. Aynı değer birden çok kez dönebilir;
    tekilleştirme çağıranın işi (`extract_unique`)."""
    if not text:
        return []
    found: list[Found] = []
    taken: list[tuple[int, int]] = []

    def overlaps(s: int, e: int) -> bool:
        return any(s < te and ts < e for ts, te in taken)

    def add(kind: str, value: str, s: int, e: int, defanged: bool = False, claim: bool = True) -> None:
        found.append(Found(kind, value, s, e, defanged))
        if claim:
            taken.append((s, e))

    # Defang işaretleri konumu bozmasın diye refang METNİN KOPYASINDA değil, eşleşme bazında
    # yapılır: önce orijinal metinde defang'li adaylar aranır.
    plain = text

    # 1. URL'ler (refang'li biçimleri dahil).
    for m in re.finditer(r"\b(?:hxxps?|h\*\*ps?|https?|fxp|ftp)(?:\[:\]|:)//[^\s<>\"'`{}|\\^]+", plain, re.I):
        raw = _strip_url(m.group(0))
        defanged = bool(_DEFANG_MARK.search(raw))
        url = normalize_url(refang(raw))
        if not url:
            continue
        host = urlsplit(url).hostname or ""
        if not (valid_domain(host) or valid_public_ip(host)):
            continue
        add("url", url, m.start(), m.start() + len(raw), defanged)
        if valid_public_ip(host):
            add("ip", host, m.start(), m.start() + len(raw), defanged, claim=False)
        else:
            add("domain", normalize_domain(host), m.start(), m.start() + len(raw), defanged, claim=False)

    # 2. E-posta (defang'li `[@]`/`[.]` dahil).
    for m in re.finditer(
        r"(?<![\w.+-])([a-z0-9][a-z0-9._%+-]{0,63})\s*(?:@|\[@\]|\(@\)|\[at\])\s*((?:" + _LABEL
        + r"(?:\.|\[\.\]|\(\.\)|\[dot\]))+[a-z]{2,24})\b",
        plain,
        re.I,
    ):
        if overlaps(m.start(), m.end()):
            continue
        raw = m.group(0)
        defanged = bool(_DEFANG_MARK.search(raw))
        domain = normalize_domain(refang(m.group(2)))
        if not valid_domain(domain):
            continue
        add("email", f"{m.group(1).lower()}@{domain}", m.start(), m.end(), defanged)
        add("domain", domain, m.start(), m.end(), defanged, claim=False)

    # 3. Kimlik biçimli göstergeler.
    for m in _CVE_RE.finditer(plain):
        add("cve", f"CVE-{m.group(1)}-{m.group(2)}", m.start(), m.end())
    for m in _ATTACK_RE.finditer(plain):
        add("attack", m.group(1), m.start(), m.end())
    for m in _ETH_RE.finditer(plain):
        if not overlaps(m.start(), m.end()):
            add("eth", m.group(1).lower(), m.start(), m.end())
    for m in _BTC_BECH_RE.finditer(plain):
        if not overlaps(m.start(), m.end()) and _bech32_ok(m.group(1)):
            add("btc", m.group(1).lower(), m.start(), m.end())
    for m in _BTC_B58_RE.finditer(plain):
        if not overlaps(m.start(), m.end()) and _base58check_ok(m.group(1)):
            add("btc", m.group(1), m.start(), m.end())
    for m in _HASH_RE.finditer(plain):
        if overlaps(m.start(), m.end()):
            continue
        value = m.group(1)
        # Yalnız rakam ya da yalnız harf olan 32+ karakterlik hex dizisi pratikte hash değildir
        # (sıra numarası, dolgu). Gerçek bir hash'te ikisi de bulunur.
        if value.isdigit() or value.isalpha() or len(set(value.lower())) < 6:
            continue
        add(_HASH_KIND[len(value)], value.lower(), m.start(), m.end())
    for m in _ASN_RE.finditer(plain):
        number = int(m.group(1))
        if _asn_public(number):
            add("asn", f"AS{number}", m.start(), m.end())

    # 4. IPv4 — defang'li biçim filtreyi atlar, düz biçim sürüm bağlamında reddedilir.
    for m in _IPV4_DEFANGED_RE.finditer(plain):
        raw = m.group(1)
        if overlaps(m.start(), m.end()):
            continue
        defanged = bool(_DEFANG_MARK.search(raw))
        value = re.sub(r"\s+", "", refang(raw))
        if not defanged:
            if not _IPV4_RE.fullmatch(value) or _ipv4_is_version(plain, m.start(1), m.end(1)):
                continue
        if valid_public_ip(value):
            add("ip", value, m.start(), m.end(), defanged)

    # 5. Alan adları — en son, çünkü URL/e-posta içindekiler zaten alındı. Defang'li biçim
    # (`twimg.co[.]uk`) düz biçimden ÖNCE: aksi halde düz tarama `twimg.co`yu alıp konumu
    # kapatıyor, gerçek gösterge kayboluyordu (gerçek veride bulundu).
    if _DEFANG_MARK.search(plain):
        for m in _DEFANGED_DOMAIN_RE.finditer(plain):
            if overlaps(m.start(), m.end()) or not _DEFANG_MARK.search(m.group(1)):
                continue
            value = normalize_domain(refang(m.group(1)))
            if valid_domain(value):
                add("domain", value, m.start(), m.end(), True)
    for m in _DOMAIN_RE.finditer(plain):
        if overlaps(m.start(), m.end()):
            continue
        value = normalize_domain(m.group(1))
        if valid_domain(value, strict=True):
            add("domain", value, m.start(), m.end())

    found.sort(key=lambda f: (f.start, f.kind))
    return found


def _asn_public(number: int) -> bool:
    if number <= 0 or number in (23456, 65535, 4294967295):
        return False
    if 64496 <= number <= 65551 or 4200000000 <= number <= 4294967294:
        return False  # belgeleme/özel kullanım aralıkları
    return number < 4294967295


@dataclass(frozen=True)
class Sighting:
    kind: str
    value: str
    context: str
    defanged: bool
    occurrences: int

    @property
    def id(self) -> str:
        return selector_id(self.kind, self.value)


def extract_unique(text: str) -> list[Sighting]:
    """Metindeki her farklı seçici bir kez — ilk geçtiği yerin bağlamıyla."""
    seen: dict[str, Sighting] = {}
    for f in extract(text):
        prev = seen.get(f.id)
        if prev is None:
            seen[f.id] = Sighting(f.kind, f.value, _context(text, f.start, f.end), f.defanged, 1)
        else:
            seen[f.id] = Sighting(prev.kind, prev.value, prev.context, prev.defanged or f.defanged, prev.occurrences + 1)
    return list(seen.values())


def detect(value: str) -> tuple[str, str] | None:
    """Tek bir değerin türü (elle giriş, hızlı pivot). Metin içinden çıkarmanın aksine bağlam
    filtresi yok: kullanıcı değeri bilerek yazdı. Dönen: (tür, normalize edilmiş değer)."""
    raw = value.strip()
    if not raw:
        return None
    text = refang(raw)
    m = _COORD_RE.match(text)
    if m:
        lat, lon = float(m.group(1)), float(m.group(2))
        if -90 <= lat <= 90 and -180 <= lon <= 180 and ("." in m.group(1) or "." in m.group(2)):
            return "coord", f"{lat:.6f},{lon:.6f}"
    if re.match(r"^(?:https?|ftp)://", text, re.I):
        url = normalize_url(_strip_url(text))
        return ("url", url) if url else None
    m = _CVE_RE.fullmatch(text)
    if m:
        return "cve", f"CVE-{m.group(1)}-{m.group(2)}"
    if _ATTACK_RE.fullmatch(text.upper()):
        return "attack", text.upper()
    m = re.fullmatch(r"ASN?\s?(\d{1,10})", text, re.I)
    if m:
        return "asn", f"AS{int(m.group(1))}"
    if _ETH_RE.fullmatch(text):
        return "eth", text.lower()
    if _BTC_BECH_RE.fullmatch(text) and _bech32_ok(text):
        return "btc", text.lower()
    if _BTC_B58_RE.fullmatch(text) and _base58check_ok(text):
        return "btc", text
    if re.fullmatch(r"[0-9a-fA-F]{32}|[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", text):
        return _HASH_KIND[len(text)], text.lower()
    try:
        ip = ipaddress.ip_address(text)
        return "ip", str(ip)
    except ValueError:
        pass
    m = _EMAIL_RE.fullmatch(text)
    if m and valid_domain(m.group(2)):
        return "email", f"{m.group(1).lower()}@{normalize_domain(m.group(2))}"
    if valid_domain(text):
        return "domain", normalize_domain(text)
    return None


def parse_id(selector: str) -> tuple[str, str]:
    kind, _, value = selector.partition(":")
    if kind not in KINDS or not value:
        raise ValueError(f"Geçersiz seçici kimliği: {selector!r}")
    return kind, value


# --- Kaynağın kendine referansı ---------------------------------------------------------

# İkinci seviye kayıt alanları: `gov.uk`, `com.tr` gibi. Tam Public Suffix List yerine bu ölçekte
# yeterli olan yaygın kalıp: ülke kodundan önce gelen kısa jenerik etiket.
_SECOND_LEVEL = {"co", "com", "gov", "org", "net", "ac", "edu", "mil", "nic", "bel", "gen", "web", "or", "ne", "go"}


def registrable_domain(host: str) -> str:
    host = normalize_domain(host)
    labels = host.split(".")
    if len(labels) >= 3 and labels[-2] in _SECOND_LEVEL and len(labels[-1]) == 2:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def is_self_reference(kind: str, value: str, own_domain: str) -> bool:
    if kind == "domain":
        host = value
    elif kind == "url":
        host = urlsplit(value).hostname or ""
    elif kind == "email":
        host = value.rsplit("@", 1)[-1]
    else:
        return False
    return bool(host) and registrable_domain(host) == own_domain
