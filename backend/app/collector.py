"""
Collector güvenlik katmanı — Q22 (kritik güvenlik sorusu).

Üç savunma katmanı, hepsi zorunlu:
    1. Allowlist  — sadece kullanıcının açıkça izin verdiği hostname'lere istek atılır.
    2. SSRF koruması — hedef IP'ler her hop'ta (ilk istek + her redirect) çözülür ve
       private/loopback/link-local/multicast/reserved aralıklar reddedilir.
    3. İçerik-veri ayrımı — toplanan içerik bu modülde ASLA yorumlanmaz/çalıştırılmaz, düz
       metin olarak döner; LLM'e "talimat" değil "güvenilmeyen veri" olarak sunulması
       görevi çağıran katmana (bkz. .claude/skills/osint-brain/) aittir.

Bilinen sınırlama (v1, bilinçli kabul edildi — bkz. Roadmap.md Faz 5 notları): DNS
rebinding'e karşı tam koruma yok. Hostname her redirect hop'unda yeniden çözülüp
doğrulanıyor, ama doğrulama ile asıl bağlantı arasında çok kısa bir pencerede DNS yanıtı
teorik olarak değişebilir. Bu, v1 için kabul edilen bir risk — tam çözüm (IP'ye pinleyip
Host header'ı elle ayarlamak) ileride gerekirse eklenebilir.
"""
import ipaddress
import json
import socket
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

ALLOWED_SCHEMES = {"http", "https"}
MAX_REDIRECTS = 3
DEFAULT_TIMEOUT = 10
MAX_BYTES = 5_000_000
MAX_OBSERVATION_TEXT_LENGTH = 20_000
USER_AGENT = "OsintLab-Collector/0.1 (personal OSINT research tool)"

# Faz 11 (dogfooding F25): sadece User-Agent göndermek yetmiyor. cisa.gov (Akamai arkasında)
# UA dışında hiçbir istemci header'ı olmayan isteğe 403 döndürüyor — UA string'i suçlu değil,
# üç tekrarda da doğrulandı: aynı UA + Accept-Language => 200, UA tek başına => 403.
# Bunlar sıradan, dürüst HTTP header'ları; kimliğimizi gizlemiyoruz (UA hâlâ kendimizi
# söylüyor), sadece isteği yarım bırakmıyoruz.
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, text/html;q=0.8, */*;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
}

ALLOWLIST_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "config" / "collector_allowlist.json"


class CollectorSecurityError(Exception):
    """Allowlist/SSRF/boyut ihlali — collector isteği reddedildi."""


class CollectorFetchError(Exception):
    """Karşı taraf isteği reddetti ya da beklenen içeriği vermedi.

    Faz 11 (dogfooding F25): bu sınıf yokken 403/404 gövdesi "içerik" sayılıyordu. Güvenlik
    ihlalinden (CollectorSecurityError) ayrı tutuluyor: orada BİZ reddediyoruz, burada
    KARŞI TARAF. İkisini aynı hataya toplamak "kendi allowlist'im mi engelledi, site mi
    engelledi" sorusunu cevapsız bırakırdı."""


def load_allowlist() -> set[str]:
    if not ALLOWLIST_PATH.is_file():
        return set()
    return set(json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8")))


def save_allowlist(hosts: set[str]) -> None:
    ALLOWLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    ALLOWLIST_PATH.write_text(json.dumps(sorted(hosts), ensure_ascii=False, indent=2), encoding="utf-8")


def is_safe_ip(ip_str: str) -> bool:
    # Negatif kategori taramasının (is_private/is_loopback/is_link_local/is_multicast/
    # is_reserved/is_unspecified) TEK BAŞINA yetersiz olduğu bulundu: 100.64.0.0/10'u
    # (RFC 6598 Shared Address Space / CGNAT — ör. Alibaba Cloud metadata servisi
    # 100.100.100.200 bu aralıkta) hiçbiri yakalamıyor, güvenli sayıyordu.
    #
    # Buna karşı önce is_global'ın TEK BAŞINA yeterli olduğu denendi ama bu daha büyük bir
    # boşluk açtı: is_global, NAT64 well-known prefix'iyle (64:ff9b::/96, RFC 6052) yazılmış
    # IPv6 adreslerini (ör. 64:ff9b::10.0.0.1, 64:ff9b::127.0.0.1) "genel" sayıyor — oysa
    # bunlar RFC1918/loopback/link-local adresler gömülü, is_reserved bunları doğru
    # yakalıyordu. DNS64/NAT64 kurulu ağlarda (bazı IPv6-only kurumsal/mobil ağlar) bu,
    # allowlist'teki bir hostname böyle bir adrese çözümlenirse SSRF korumasını atlatabilirdi.
    #
    # Doğru çözüm: ikisi birden. Negatif liste NAT64/6to4/Teredo gibi IANA-reserved sentetik
    # IPv6 önekleri için gerekli (is_reserved), is_global ise CGNAT gibi negatif listenin
    # kaçırdığı aralıklar için gerekli — biri diğerinin yerine geçmiyor.
    ip = ipaddress.ip_address(ip_str)
    return (
        not ip.is_private
        and not ip.is_loopback
        and not ip.is_link_local
        and not ip.is_multicast
        and not ip.is_reserved
        and not ip.is_unspecified
        and ip.is_global
    )


def normalize_hostname(value: str) -> str:
    """Allowlist'e yazılmadan önce hostname'i kanonikleştirir.

    Faz 11 (dogfooding F6, önlem): allowlist alanına tam URL yapıştırmak çok muhtemel bir
    hata — o hâliyle kaydedilirse hiçbir zaman eşleşmez ve sebebi ekranda görünmez."""
    value = value.strip().lower()
    if "//" in value or value.startswith(("http:", "https:")):
        parsed = urlparse(value if "//" in value else f"//{value}")
        value = parsed.hostname or value
    value = value.split("/")[0].split("@")[-1]
    if value.count(":") == 1:  # port (IPv6 değil)
        value = value.split(":")[0]
    return value.rstrip(".")


def _host_allowed(hostname: str, allowlist: set[str]) -> bool:
    """Faz 11 (dogfooding F4): allowlist'te 'theverge.com' varken feed 'www.theverge.com'da
    olduğu için tarama reddediliyordu — kullanıcı doğru siteyi eklemiş olmasına rağmen.

    Kapsam bilerek DAR tutuldu: yalnızca tam olarak 'www.' prefix'i, iki yönlü. Genel bir
    subdomain wildcard'ı (*.example.com) DEĞİL — o, allowlist'in tüm amacını (kullanıcının
    açıkça izin verdiği host) zayıflatır ve alt alan devralma riskini içeri alır. 'www' ise
    alan sahibinin kanonik host'unun kendisidir, ayrı bir taraf değil."""
    if hostname in allowlist:
        return True
    if hostname.startswith("www."):
        return hostname[4:] in allowlist
    return f"www.{hostname}" in allowlist


def _validate_hop(url: str, allowlist: set[str]) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise CollectorSecurityError(f"İzin verilmeyen scheme: {parsed.scheme!r}")
    hostname = parsed.hostname
    if not hostname:
        raise CollectorSecurityError("URL'de hostname yok")
    if not _host_allowed(hostname, allowlist):
        raise CollectorSecurityError(
            f"Reddedildi: {hostname!r} allowlist'te değil — Toplayıcılar sayfasından ekleyebilirsin."
        )
    try:
        infos = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise CollectorSecurityError(f"DNS çözümlenemedi: {exc}") from exc
    resolved_ips = {info[4][0] for info in infos}
    for ip_str in resolved_ips:
        if not is_safe_ip(ip_str):
            raise CollectorSecurityError(
                f"Reddedildi: {hostname!r} genel-olmayan bir adrese çözümleniyor ({ip_str}) — SSRF koruması"
            )
    return hostname


def safe_fetch(url: str, allowlist: set[str]) -> tuple[str, bytes, str]:
    """Allowlist + SSRF doğrulaması yapılmış GET isteği. Her redirect hop'u ayrıca doğrulanır
    (yönlendirme zinciriyle korumayı atlatmak mümkün olmasın diye). Dönen: (final_url, content, content_type)."""
    current_url = url
    for _ in range(MAX_REDIRECTS + 1):
        _validate_hop(current_url, allowlist)
        response = requests.get(
            current_url,
            timeout=DEFAULT_TIMEOUT,
            allow_redirects=False,
            stream=True,
            headers=DEFAULT_HEADERS,
        )
        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get("Location")
            response.close()
            if not location:
                raise CollectorSecurityError("Location header'sız redirect")
            current_url = urljoin(current_url, location)
            continue

        content = bytearray()
        for chunk in response.iter_content(chunk_size=65536):
            content.extend(chunk)
            if len(content) > MAX_BYTES:
                response.close()
                raise CollectorSecurityError(f"Yanıt çok büyük (> {MAX_BYTES} byte)")
        content_type = response.headers.get("Content-Type", "")

        # Faz 11 (F25): 4xx/5xx gövdesi ASLA içerik değildir. Bu kontrol yokken cisa.gov'un
        # 403 "Access Denied" sayfası (410 byte HTML) feed sanılıp parse ediliyor, 0 item
        # çıkıyor ve arayüz "Kaynakta 0 öğe" diyordu — yani "site seni engelledi" ile
        # "kaynakta yeni haber yok" ayırt edilemiyordu. `web` modunda daha da kötüsü olurdu:
        # engelleme sayfası kalıcı bir Observation olarak graf'a girerdi.
        if response.status_code >= 400:
            hostname = urlparse(current_url).hostname or current_url
            # Durum koduna göre AYRI teşhis: "engellendin", "adres yok" ve "site arızalı"
            # kullanıcı için tamamen farklı eylemler gerektiriyor. Hepsine aynı cümleyi
            # yazmak, düzeltmeye çalıştığımız belirsizliği bir katman yukarıda tekrar üretir.
            if response.status_code in (401, 403, 429):
                teshis = "kaynak otomatik erişimi engelledi (kaynakta içerik yok demek DEĞİL)"
            elif response.status_code == 404:
                teshis = "böyle bir adres yok — feed adresini kontrol et"
            elif response.status_code >= 500:
                teshis = "kaynağın kendi sunucusu arızalı, sonra tekrar dene"
            else:
                teshis = "istek kabul edilmedi"
            raise CollectorFetchError(
                f"{hostname} {response.status_code} döndü: {teshis}. "
                f"(Yanıt gövdesi {len(content)} byte, {content_type or 'tür belirtilmemiş'} — "
                "içerik olarak kaydedilmedi.)"
            )

        return current_url, bytes(content), content_type

    raise CollectorSecurityError("Çok fazla redirect")


def _truncate(text: str) -> str:
    if len(text) <= MAX_OBSERVATION_TEXT_LENGTH:
        return text
    return text[:MAX_OBSERVATION_TEXT_LENGTH] + "\n[...kesildi, orijinal daha uzun...]"


def extract_text_from_html(html: bytes | str) -> str:
    """Toplanan içerik burada YALNIZCA düz metne çevrilir — script/style çalıştırılmaz,
    hiçbir HTML/JS içeriği işlenmez ya da değerlendirilmez (içerik-veri ayrımı).

    Faz 11 (dogfooding F21): sayfanın iskeleti (nav/menü/footer/tema seçici) içerik değil,
    gürültüdür. Bir portfolyo sayfasında çıkarılan 137 satırın 74'ü tekrardı ("→" 13 kez,
    "Opens in a new tab" 7 kez, menü öğeleri 3-5 kez). Bu yalnızca okunabilirlik sorunu
    değil: Faz 7 change detection içeriği karşılaştırdığı için, site menüsünü değiştirdiğinde
    tüm sayfa "değişmiş" sayılıp yanlış alarm üretirdi.

    Strateji: semantic HTML'e güven — <main>/<article> varsa onu al, yoksa gövdeden iskeleti
    çıkar. Sonuç şüpheli derecede kısaysa (JS ile dolan bir kabuk olabilir) tüm gövdeye dön."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    def collect(node) -> str:
        raw = node.get_text(separator="\n")
        return "\n".join(line.strip() for line in raw.splitlines() if line.strip())

    full = collect(soup)
    root = soup.find("main") or soup.find("article")
    if root is not None:
        text = collect(root)
    else:
        for tag in soup(["nav", "header", "footer", "aside"]):
            tag.decompose()
        text = collect(soup)

    # Güvenlik ağı: daraltma içeriğin neredeyse tamamını yediyse ham gövdeye dön.
    if len(text) < 200 and len(full) > len(text):
        text = full
    return _truncate(text)


# --- Faz 25: makale ayrıştırma -------------------------------------------------
#
# `extract_text_from_html` sayfayı DARALTIR (iskeleti atar) ama yine de "sayfanın metni"ni
# döndürür. Faz 24'te toplanan tek `mode=web` gözlemi bunun bedelini ölçülebilir kıldı:
# 9370 karakter, ilk satırı "Personal Tech" (sitenin bölüm menüsü) ve tek başına 57 entity
# adayı üretti. Sorun toplayıcıda değil, ayrıştırmadaydı — `Claim.text` sayfanın tamamı
# oluyordu.
#
# Buradaki ayrıştırma iki şeyi ayırır: BAŞLIK ve GÖVDE. İkisi de deterministik, yeni bağımlılık
# yok (readability/trafilatura eklenmedi — bkz. Roadmap Faz 25).
#
# Gövde seçimi iki kanıta dayanır, ikisi de site-bağımsız:
#   1. **Paragraf yoğunluğu.** Makale gövdesi, uzun <p>'lerin toplandığı düğümdür. Her aday
#      düğüm kendi altındaki uzun paragrafların uzunluk toplamıyla puanlanır; en yüksek puana
#      yakın olanlar arasından EN DERİN olan seçilir (ata düğümler her zaman en az çocukları
#      kadar puan alır, o yüzden "en derin" olmadan hep <body> kazanırdı).
#   2. **Bağlantı yoğunluğu.** Ölçüldü: register sayfasında gövde doğru bulunduğu halde
#      metin hâlâ 9312 karakterdi, çünkü makalenin İÇİNE serpilmiş "ilgili haber" listeleri
#      (<ul><li><a><h3>) de gövdenin içindeydi. Bunların metninin ~%100'ü bir bağlantının
#      içindedir; gerçek paragrafların ise küçük bir kısmı. Bağlantı oranı eşiği geçen ya da
#      tamamen bir <a>'nın içinde duran bloklar atılır — 9312 → 4760, makalenin kendisi.
#
# Sonuç yine Q22 sınırı içinde ham veridir; yalnızca daha dar bir ham veri.
ARTICLE_SKELETON_TAGS = [
    "nav", "header", "footer", "aside", "form", "iframe", "svg", "button", "figure",
    "figcaption",
]
ARTICLE_BLOCK_TAGS = ("p", "h2", "h3", "h4", "li", "blockquote", "pre")
# Puanlamaya giren paragrafın asgari uzunluğu. Kısa <p>'ler ("Paylaş", "3 dk okuma") her
# sayfada var ve bir menüyü makale sanmaya yeter.
ARTICLE_MIN_PARAGRAPH = 40
# Gövdeye alınacak satırın asgari uzunluğu.
ARTICLE_MIN_LINE = 25
ARTICLE_MAX_LINK_DENSITY = 0.5
# Gövde adayları arasında "en yüksek puana yakın" sayılma oranı: eşit puanlı sarmalayıcılar
# arasında en derini seçilirken küçük farkların (bir kenar paragrafı) seçimi yukarı
# kaydırmasını engeller.
ARTICLE_SCORE_TOLERANCE = 0.95


def _normalized_text(node) -> str:
    return " ".join(node.get_text(separator=" ").split())


def _link_density(node) -> float:
    """Düğüm metninin ne kadarı bir bağlantının içinde. 1.0 = tamamı link (menü/teaser)."""
    total = len(_normalized_text(node))
    if not total:
        return 1.0
    return sum(len(_normalized_text(a)) for a in node.find_all("a")) / total


def _is_content_block(node) -> bool:
    """Bu blok makale metni mi, yoksa bağlantı listesi/sarmalayıcı mı."""
    if node.find_parent("a") is not None:
        return False
    # Başka blok içeriyorsa kendisi bir sarmalayıcıdır; çocukları zaten ayrı ayrı gelecek.
    if node.find(ARTICLE_BLOCK_TAGS) is not None:
        return False
    return _link_density(node) < ARTICLE_MAX_LINK_DENSITY


def extract_article_from_html(html: bytes | str) -> tuple[str, str]:
    """(başlık, gövde) — gövde bulunamazsa ("...", "") döner ve çağıran fallback'e düşer.

    Başlık sırası <h1> → og:title → <title>. <h1> önce çünkü <title> çoğu sitede
    "Başlık | Site Adı" biçiminde ve site adı her claim'in başına yapışırdı."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    title = ""
    h1 = soup.find("h1")
    if h1 is not None:
        title = _normalized_text(h1)
    if not title:
        meta = soup.find("meta", attrs={"property": "og:title"})
        if meta and meta.get("content"):
            title = " ".join(meta["content"].split())
    if not title and soup.title:
        title = " ".join(soup.title.get_text().split())

    for tag in soup(ARTICLE_SKELETON_TAGS):
        tag.decompose()

    scored: list[tuple[int, object]] = []
    for node in soup.find_all(["article", "main", "div", "section", "td"]):
        score = 0
        for paragraph in node.find_all("p"):
            text = _normalized_text(paragraph)
            if len(text) >= ARTICLE_MIN_PARAGRAPH and _is_content_block(paragraph):
                score += len(text)
        if score:
            scored.append((score, node))
    if not scored:
        return title, ""

    best = max(score for score, _ in scored)
    near_best = [node for score, node in scored if score >= best * ARTICLE_SCORE_TOLERANCE]
    root = max(near_best, key=lambda node: len(list(node.parents)))

    seen: set[str] = set()
    lines: list[str] = []
    for node in root.find_all(ARTICLE_BLOCK_TAGS):
        text = _normalized_text(node)
        if len(text) < ARTICLE_MIN_LINE or text in seen:
            continue
        if not _is_content_block(node):
            continue
        seen.add(text)
        lines.append(text)
    return title, "\n".join(lines)


def extract_content_from_html(html: bytes | str) -> str:
    """`mode=web`in gözleme yazdığı metin: başlık + gövde.

    Gövde çıkmazsa (makale olmayan bir sayfa — ör. bir gazetenin ana sayfası) eski davranışa,
    yani daraltılmış tam sayfa metnine düşülür. Kaybetmek, ayrıştıramamaktan kötüdür: o
    gözlemi tamamen boş kaydetmek kullanıcıya "site boştu" derdi."""
    title, body = extract_article_from_html(html)
    if not body:
        return extract_text_from_html(html)
    return _truncate(f"{title}\n\n{body}".strip() if title else body)


def _entry_published(entry) -> datetime | None:
    """RSS/Atom yayın tarihini timezone-aware UTC datetime'a çevirir.

    Faz 11 (dogfooding) bulgusu F1: bu tarih daha önce string olarak çıkarılıp hiçbir yerde
    tüketilmiyordu, dolayısıyla arşivden gelen 2023 tarihli bir duyuru da dünkü duyuru da
    "bugün gözlendi" olarak kaydediliyordu — temporal analiz (Faz 2 supersede, Faz 7 "son 30
    günde ne değişti") gerçek veride anlamsızlaşıyordu. feedparser'ın *_parsed alanları
    struct_time'ı zaten UTC'ye normalize eder; ham string'i elle ayrıştırmaktan güvenilir."""
    for key in ("published_parsed", "updated_parsed"):
        value = entry.get(key)
        if value:
            try:
                return datetime(*value[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                continue
    return None


def _clean_feed_text(value: str) -> str:
    """RSS başlık/özetleri düz metin değildir: HTML etiketi ve karakter entity'si taşırlar.

    Faz 11 (dogfooding F13): Verge'in özeti sisteme `OpenAI&#8217;s Astra release ... [&#8230;]`
    olarak girmişti. Bu metin sonra Claim.text'e aynen kopyalanıyor, yani kirlilik graf'ın
    kalıcı katmanına sızıyordu. get_text() hem etiketi ayıklar hem entity'yi çözer."""
    if not value:
        return ""
    return BeautifulSoup(value, "html.parser").get_text(separator=" ").strip()


def parse_rss(content: bytes) -> list[dict]:
    parsed = feedparser.parse(content)
    items = []
    for entry in parsed.entries:
        text = f"{_clean_feed_text(entry.get('title', ''))}\n\n{_clean_feed_text(entry.get('summary', ''))}"
        items.append({
            "text": _truncate(text.strip()),
            "link": entry.get("link", ""),
            "published": _entry_published(entry),
        })
    return items
