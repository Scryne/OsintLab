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
import logging
import socket
import threading
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

from app.db import DATA_ROOT, atomic_write_text

logger = logging.getLogger(__name__)

ALLOWED_SCHEMES = {"http", "https"}
MAX_REDIRECTS = 3
DEFAULT_TIMEOUT = 10
MAX_BYTES = 5_000_000
# Bir isteğin TOPLAM süresi. `requests`in `timeout`u yalnızca bağlanma ve TEK BİR okuma
# arasındaki boşluğu sınırlar; veriyi damla damla gönderen bir sunucu her chunk'ta sayacı
# sıfırlar ve istek sonsuza kadar sürebilir. Faz 26'nın ilk toplu doğrulamasında ölçüldü:
# 55 kaynaklık tur 48. kayıtta takıldı ve 11 dakika boyunca hiç ilerlemedi. Tek bir yavaş
# sunucunun bütün turu kilitlemesi, zamanlanmış taramayı da (Faz 12) aynı şekilde
# durdurabilirdi — bu yüzden sınır collector'ün kendisinde, çağıranlarda değil.
MAX_FETCH_SECONDS = 45
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

# Veri kökünün altında: izole bir test kökü (`OSINTLAB_DATA_DIR`) gerçek allowlist'e dokunmasın.
ALLOWLIST_PATH = DATA_ROOT / "config" / "collector_allowlist.json"


class CollectorSecurityError(Exception):
    """Allowlist/SSRF/boyut ihlali — collector isteği reddedildi."""


class CollectorFetchError(Exception):
    """Karşı taraf isteği reddetti ya da beklenen içeriği vermedi.

    Faz 11 (dogfooding F25): bu sınıf yokken 403/404 gövdesi "içerik" sayılıyordu. Güvenlik
    ihlalinden (CollectorSecurityError) ayrı tutuluyor: orada BİZ reddediyoruz, burada
    KARŞI TARAF. İkisini aynı hataya toplamak "kendi allowlist'im mi engelledi, site mi
    engelledi" sorusunu cevapsız bırakırdı.

    `status_code`: karşı tarafın HTTP cevabı; bağlantı hiç kurulamadıysa (DNS, zaman aşımı,
    TLS) None. Arşiv doğrulaması "sayfa kalıcı olarak yok" (404/410) ile "şu an ulaşılamıyor"
    ayrımını buna bakarak yapıyor."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def load_allowlist() -> set[str]:
    if not ALLOWLIST_PATH.is_file():
        return set()
    try:
        hosts = json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # Bozuk dosya bütün toplamayı beklenmedik bir istisnayla düşürüyordu. Güvenli taraf
        # boş allowlist: her istek "allowlist'te değil" diye reddedilir ve sebep görünür.
        logger.exception("Allowlist okunamadı (%s) — boş kabul ediliyor", ALLOWLIST_PATH)
        return set()
    return {h for h in hosts if isinstance(h, str)} if isinstance(hosts, list) else set()


def save_allowlist(hosts: set[str]) -> None:
    atomic_write_text(ALLOWLIST_PATH, json.dumps(sorted(hosts), ensure_ascii=False, indent=2))


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


def _session() -> requests.Session:
    """Ortamdan proxy/.netrc OKUMAYAN bir oturum. `requests` varsayılan olarak `.netrc`'deki
    kimlik bilgilerini eşleşen host'a gönderir ve `HTTP(S)_PROXY`yi izler — toplanan adresler
    dış feed'lerden geldiği için ikisi de istenmeyen bir sızıntı/yönlendirme yüzeyi."""
    session = requests.Session()
    session.trust_env = False
    return session


def safe_fetch(
    url: str,
    allowlist: set[str],
    *,
    headers: dict[str, str] | None = None,
    max_bytes: int | None = None,
    max_seconds: float | None = None,
    timeout: float | None = None,
) -> tuple[str, bytes, str]:
    """Allowlist + SSRF doğrulaması yapılmış GET isteği. Her redirect hop'u ayrıca doğrulanır
    (yönlendirme zinciriyle korumayı atlatmak mümkün olmasın diye). Dönen: (final_url, content, content_type).

    Ağ katmanının kendi hataları (DNS, bağlantı reddi, TLS, zaman aşımı) `CollectorFetchError`a
    çevrilir. 2026-10-18 denetiminde bulundu: bunlar ham `requests` istisnası olarak sızıyordu ve
    her çağıran yalnızca iki collector hatasını yakaladığı için zamanlanmış tarama hatayı
    KAYDETMEDEN çöküyordu — `last_run_at` ilerlemiyor, tarama her dakika yeniden deneniyor,
    `consecutive_failures` hiç artmıyor ve SCAN_FAILED bildirimi hiç düşmüyordu (logda
    "beklenmedik şekilde çöktü" olarak görülüyordu).

    Faz 30: zenginleştirme modülleri aynı güvenlik katmanından geçiyor ama kendi başlıklarına
    (DoH `Accept: application/dns-json`), boyut sınırına (ATT&CK veri seti 55 MB) ve süresine
    ihtiyaç duyuyor. Verilmezse modül sabitleri geçerli — testlerin değiştirdiği değerler de
    çağrı anında okunuyor."""
    deadline = time.monotonic() + (MAX_FETCH_SECONDS if max_seconds is None else max_seconds)
    request_headers = DEFAULT_HEADERS if headers is None else {**DEFAULT_HEADERS, **headers}
    limit = MAX_BYTES if max_bytes is None else max_bytes
    with _session() as session:
        current_url = url
        for _ in range(MAX_REDIRECTS + 1):
            _validate_hop(current_url, allowlist)
            hostname = urlparse(current_url).hostname or current_url
            try:
                response = session.get(
                    current_url,
                    timeout=DEFAULT_TIMEOUT if timeout is None else timeout,
                    allow_redirects=False,
                    stream=True,
                    headers=request_headers,
                )
            except requests.RequestException as exc:
                raise CollectorFetchError(
                    f"{hostname} adresine ulaşılamadı ({type(exc).__name__}) — ağ, DNS ya da "
                    "kaynağın sunucusu yanıt vermiyor; sonra tekrar denenecek."
                ) from exc
            try:
                if response.status_code in (301, 302, 303, 307, 308):
                    location = response.headers.get("Location")
                    if not location:
                        raise CollectorSecurityError("Location header'sız redirect")
                    current_url = urljoin(current_url, location)
                    continue
                content = _read_body(response, hostname, deadline, limit, max_seconds)
            finally:
                response.close()
            return _finish(response, current_url, content)

    raise CollectorSecurityError("Çok fazla redirect")


def _read_body(
    response: requests.Response, hostname: str, deadline: float, limit: int | None = None, seconds: float | None = None
) -> bytes:
    """Gövdeyi boyut ve TOPLAM süre sınırıyla okur.

    Süre yalnızca chunk'lar ARASINDA kontrol edilseydi yetmezdi: `read(65536)` 64 KiB dolana
    kadar bloklar ve her soket okuması `DEFAULT_TIMEOUT`u sıfırlar — 9 sn'de bir bayt yollayan
    bir sunucu tek bir iterasyonu günlerce sürdürebilir. Bir bekçi zamanlayıcı süre dolunca
    bağlantıyı dışarıdan kapatır; okuma o anda patlar ve süre aşımı olarak raporlanır."""
    timed_out = threading.Event()

    def _expire() -> None:
        timed_out.set()
        response.close()

    remaining = max(0.0, deadline - time.monotonic())
    watchdog = threading.Timer(remaining, _expire)
    watchdog.daemon = True
    watchdog.start()
    content = bytearray()
    try:
        for chunk in response.iter_content(chunk_size=65536):
            content.extend(chunk)
            if len(content) > (MAX_BYTES if limit is None else limit):
                raise CollectorSecurityError(f"Yanıt çok büyük (> {MAX_BYTES if limit is None else limit} byte)")
            if timed_out.is_set():
                break
    except (requests.RequestException, OSError, AttributeError, ValueError) as exc:
        if not timed_out.is_set():
            raise CollectorFetchError(
                f"{hostname} yanıtı okunurken bağlantı koptu ({type(exc).__name__})."
            ) from exc
    finally:
        watchdog.cancel()
    if timed_out.is_set():
        raise CollectorFetchError(
            f"{hostname} yanıtı {MAX_FETCH_SECONDS if seconds is None else seconds} saniyede bitmedi — sunucu içeriği çok "
            "yavaş gönderiyor, istek bırakıldı."
        )
    return bytes(content)


def _finish(response: requests.Response, current_url: str, content: bytes) -> tuple[str, bytes, str]:
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
        elif response.status_code in (404, 410):
            teshis = "böyle bir adres yok — feed adresini kontrol et"
        elif response.status_code >= 500:
            teshis = "kaynağın kendi sunucusu arızalı, sonra tekrar dene"
        else:
            teshis = "istek kabul edilmedi"
        raise CollectorFetchError(
            f"{hostname} {response.status_code} döndü: {teshis}. "
            f"(Yanıt gövdesi {len(content)} byte, {content_type or 'tür belirtilmemiş'} — "
            "içerik olarak kaydedilmedi.)",
            status_code=response.status_code,
        )

    return current_url, content, content_type


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


def _entry_link(raw: str, base_url: str | None) -> str:
    """Feed öğesinin bağlantısı, mutlak ve yalnızca http(s).

    Feed'ler göreli bağlantı (`/2026/10/haber`) ya da `javascript:`/`mailto:` taşıyabiliyor.
    Olduğu gibi saklanınca arşiv doğrulaması ve yeniden ayrıştırma sonradan "izin verilmeyen
    scheme" ile düşüyor ve bu ERISILEMEDI sayılıp kanıt bağını koparıyordu. Kullanılamayan
    bağlantı boş döner; çağıran feed adresine düşer."""
    link = (raw or "").strip()
    if not link:
        return ""
    if base_url:
        link = urljoin(base_url, link)
    return link if urlparse(link).scheme in ALLOWED_SCHEMES else ""


def parse_rss(content: bytes, base_url: str | None = None) -> list[dict]:
    parsed = feedparser.parse(content)
    items = []
    for entry in parsed.entries:
        text = f"{_clean_feed_text(entry.get('title', ''))}\n\n{_clean_feed_text(entry.get('summary', ''))}"
        items.append({
            "text": _truncate(text.strip()),
            "link": _entry_link(entry.get("link", ""), base_url),
            "published": _entry_published(entry),
        })
    return items


# --- v6: Telegram herkese açık kanal önizlemesi ------------------------------------------
#
# `https://t.me/s/<kanal>` Telegram'ın kendi herkese açık web önizlemesi: giriş istemez, yalnızca
# önizlemesi açık kanalları gösterir (son ~20 mesaj). OSINT'te tehdit aktörü, hacktivist ve haber
# kanallarını izlemenin standart yolu. Kişi hesabı ya da özel grup değil, herkese açık YAYIN —
# yani bir RSS feed'i ile aynı sınıf (Q25 kapsam sınırı içinde).
#
# Ayrıştırma da RSS gibi yalnızca yapılandırılmış alanlar: mesajın kalıcı bağlantısı
# (`data-post="kanal/123"` → `https://t.me/kanal/123`), zamanı (`<time datetime>`) ve metni.
# Medya indirilmez; yalnızca "fotoğraf/video var" diye not düşülür.
TELEGRAM_HOST = "t.me"


def telegram_preview_url(value: str) -> str | None:
    """`@kanal`, `t.me/kanal`, `https://t.me/s/kanal` → `https://t.me/s/kanal`."""
    import re as _re

    value = value.strip()
    m = _re.match(r"^(?:https?://)?(?:www\.)?t(?:elegram)?\.me/(?:s/)?([A-Za-z0-9_]{4,64})/?(?:\?.*)?$", value) or \
        _re.match(r"^@?([A-Za-z0-9_]{4,64})$", value)
    return f"https://t.me/s/{m.group(1)}" if m else None


def parse_telegram(html_bytes: bytes) -> list[dict]:
    soup = BeautifulSoup(html_bytes, "html.parser")
    items = []
    for msg in soup.select("div.tgme_widget_message[data-post]"):
        post = msg.get("data-post") or ""
        if "/" not in post:
            continue
        text_node = msg.select_one(".tgme_widget_message_text")
        text = ""
        if text_node is not None:
            # Satır sonları <br> ile geliyor; bağlantı/kalın gibi satır içi etiketlerde ayırıcı
            # kullanmak cümleleri satırlara bölüyordu (gerçek bir kanalda görüldü).
            for br in text_node.find_all("br"):
                br.replace_with("\n")
            text = "\n".join(" ".join(line.split()) for line in text_node.get_text().splitlines()).strip()
        media = []
        if msg.select_one(".tgme_widget_message_photo_wrap"):
            media.append("fotoğraf")
        if msg.select_one(".tgme_widget_message_video_player"):
            media.append("video")
        if msg.select_one(".tgme_widget_message_document"):
            media.append("dosya")
        preview = msg.select_one(".tgme_widget_message_link_preview")
        if preview is not None and preview.get("href"):
            text += f"\n[bağlantı önizlemesi: {preview.get('href')}]"
        if not text and not media:
            continue
        published = None
        time_node = msg.select_one("time[datetime]")
        if time_node is not None:
            try:
                published = datetime.fromisoformat(time_node["datetime"]).astimezone(timezone.utc)
            except ValueError:
                published = None
        channel = post.split("/")[0]
        header = f"[Telegram @{channel}]" + (f" ({', '.join(media)})" if media else "")
        items.append({
            "text": _truncate(f"{header}\n{text}".strip()),
            "link": f"https://t.me/{post}",
            "published": published,
        })
    return items
