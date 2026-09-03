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

ALLOWLIST_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "config" / "collector_allowlist.json"


class CollectorSecurityError(Exception):
    """Allowlist/SSRF/boyut ihlali — collector isteği reddedildi."""


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
            headers={"User-Agent": USER_AGENT},
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
        return current_url, bytes(content), content_type

    raise CollectorSecurityError("Çok fazla redirect")


def _truncate(text: str) -> str:
    if len(text) <= MAX_OBSERVATION_TEXT_LENGTH:
        return text
    return text[:MAX_OBSERVATION_TEXT_LENGTH] + "\n[...kesildi, orijinal daha uzun...]"


def extract_text_from_html(html: bytes | str) -> str:
    """Toplanan içerik burada YALNIZCA düz metne çevrilir — script/style çalıştırılmaz,
    hiçbir HTML/JS içeriği işlenmez ya da değerlendirilmez (içerik-veri ayrımı)."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return _truncate("\n".join(lines))


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
