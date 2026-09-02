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


def _validate_hop(url: str, allowlist: set[str]) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise CollectorSecurityError(f"İzin verilmeyen scheme: {parsed.scheme!r}")
    hostname = parsed.hostname
    if not hostname:
        raise CollectorSecurityError("URL'de hostname yok")
    if hostname not in allowlist:
        raise CollectorSecurityError(f"Reddedildi: {hostname!r} allowlist'te değil")
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


def parse_rss(content: bytes) -> list[dict]:
    parsed = feedparser.parse(content)
    items = []
    for entry in parsed.entries:
        text = f"{entry.get('title', '')}\n\n{entry.get('summary', '')}"
        items.append({
            "text": _truncate(text.strip()),
            "link": entry.get("link", ""),
            "published": entry.get("published", ""),
        })
    return items
