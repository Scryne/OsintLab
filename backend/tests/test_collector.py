"""Collector güvenlik katmanı (Q22) ve ayrıştırıcılar — ağa ÇIKMADAN.

Ağ çağrıları sahte yanıtlarla değiştiriliyor: testin amacı bizim kodumuzun hata/süre/boyut
sınırlarındaki davranışı, dış sitelerin o anki durumu değil."""
import time

import pytest
import requests

from app import collector
from app.collector import (
    CollectorFetchError,
    CollectorSecurityError,
    _entry_link,
    _host_allowed,
    extract_article_from_html,
    is_safe_ip,
    normalize_hostname,
    parse_rss,
    safe_fetch,
)


@pytest.mark.parametrize(
    "ip, safe",
    [
        ("8.8.8.8", True),
        ("127.0.0.1", False),
        ("10.1.2.3", False),
        ("192.168.0.10", False),
        ("169.254.169.254", False),  # bulut metadata
        ("100.100.100.200", False),  # CGNAT — negatif liste tek başına kaçırıyordu
        ("::1", False),
        ("64:ff9b::7f00:1", False),  # NAT64 içine gömülü loopback — is_global tek başına kaçırıyordu
        ("2606:4700:4700::1111", True),
    ],
)
def test_is_safe_ip(ip, safe):
    assert is_safe_ip(ip) is safe


def test_normalize_hostname_handles_urls_and_case():
    assert normalize_hostname("https://WWW.Example.com/feed?x=1") == "www.example.com"
    assert normalize_hostname("example.com.") == "example.com"
    assert normalize_hostname("example.com:8080") == "example.com"


def test_host_allowed_only_www_tolerance():
    allow = {"example.com"}
    assert _host_allowed("example.com", allow)
    assert _host_allowed("www.example.com", allow)
    assert not _host_allowed("evil.example.com", allow)


def test_entry_link_resolves_relative_and_drops_bad_schemes():
    base = "https://site.com/feed/"
    assert _entry_link("/2026/haber", base) == "https://site.com/2026/haber"
    assert _entry_link("javascript:alert(1)", base) == ""
    assert _entry_link("mailto:x@y.z", base) == ""
    assert _entry_link("", base) == ""


def test_parse_rss_uses_base_url_for_relative_links():
    feed = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>
    <item><title>Baslik &amp; detay</title><link>/a/b</link><description>&lt;p&gt;Ozet&lt;/p&gt;</description>
    <pubDate>Mon, 06 Sep 2026 10:00:00 GMT</pubDate></item></channel></rss>"""
    items = parse_rss(feed, "https://news.example.com/rss")
    assert items[0]["link"] == "https://news.example.com/a/b"
    assert items[0]["text"].startswith("Baslik & detay")
    assert "<p>" not in items[0]["text"]
    assert items[0]["published"].tzinfo is not None


def test_extract_article_drops_link_lists():
    body = "Bu paragraf makalenin asıl gövdesidir ve yeterince uzun bir cümle içerir. " * 3
    html = f"""<html><head><title>Site | X</title></head><body>
    <h1>Gerçek Başlık</h1>
    <div><ul>{''.join(f'<li><a href="/{i}">İlgili haber bağlantısı numara {i} burada</a></li>' for i in range(8))}</ul></div>
    <article><p>{body}</p><p>{body}</p></article></body></html>"""
    title, text = extract_article_from_html(html)
    assert title == "Gerçek Başlık"
    assert "makalenin asıl gövdesidir" in text
    assert "İlgili haber" not in text


class _FakeResponse:
    def __init__(self, status=200, chunks=(b"ok",), headers=None, delay=0.0):
        self.status_code = status
        self.headers = headers or {"Content-Type": "text/html"}
        self._chunks = chunks
        self._delay = delay
        self.closed = False

    def iter_content(self, chunk_size=65536):
        for chunk in self._chunks:
            if self.closed:
                raise requests.exceptions.ConnectionError("closed")
            time.sleep(self._delay)
            if self.closed:
                raise requests.exceptions.ConnectionError("closed")
            yield chunk

    def close(self):
        self.closed = True


class _FakeSession:
    def __init__(self, behaviour):
        self.behaviour = behaviour
        self.trust_env = True

    def get(self, url, **kwargs):
        if isinstance(self.behaviour, Exception):
            raise self.behaviour
        return self.behaviour

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def no_dns(monkeypatch):
    monkeypatch.setattr(collector, "_validate_hop", lambda url, allow: "example.com")


def test_safe_fetch_wraps_network_errors(no_dns, monkeypatch):
    # Önceden ham requests istisnası sızıyor ve zamanlanmış tarama hatayı KAYDETMEDEN çöküyordu.
    monkeypatch.setattr(collector, "_session", lambda: _FakeSession(requests.exceptions.ConnectionError("boom")))
    with pytest.raises(CollectorFetchError) as info:
        safe_fetch("https://example.com/feed", {"example.com"})
    assert info.value.status_code is None


def test_safe_fetch_reports_status_code(no_dns, monkeypatch):
    monkeypatch.setattr(collector, "_session", lambda: _FakeSession(_FakeResponse(status=404, chunks=(b"nope",))))
    with pytest.raises(CollectorFetchError) as info:
        safe_fetch("https://example.com/x", {"example.com"})
    assert info.value.status_code == 404


def test_safe_fetch_enforces_size_limit(no_dns, monkeypatch):
    monkeypatch.setattr(collector, "MAX_BYTES", 10)
    monkeypatch.setattr(collector, "_session", lambda: _FakeSession(_FakeResponse(chunks=(b"0123456789", b"x"))))
    with pytest.raises(CollectorSecurityError):
        safe_fetch("https://example.com/x", {"example.com"})


def test_safe_fetch_total_deadline_cuts_slow_servers(no_dns, monkeypatch):
    # Damla damla gönderen sunucu: her chunk arası zaman aşımından kısa ama toplam süre sınırı aşar.
    monkeypatch.setattr(collector, "MAX_FETCH_SECONDS", 0.3)
    slow = _FakeResponse(chunks=[b"a"] * 50, delay=0.05)
    monkeypatch.setattr(collector, "_session", lambda: _FakeSession(slow))
    started = time.monotonic()
    with pytest.raises(CollectorFetchError, match="saniyede bitmedi"):
        safe_fetch("https://example.com/slow", {"example.com"})
    assert time.monotonic() - started < 2.0


def test_validate_hop_rejects_non_allowlisted_and_private(monkeypatch):
    with pytest.raises(CollectorSecurityError, match="allowlist"):
        collector._validate_hop("https://evil.com/", {"example.com"})
    monkeypatch.setattr(collector.socket, "getaddrinfo", lambda *a, **k: [(None, None, None, None, ("10.0.0.5", 443))])
    with pytest.raises(CollectorSecurityError, match="SSRF"):
        collector._validate_hop("https://example.com/", {"example.com"})
    with pytest.raises(CollectorSecurityError, match="scheme"):
        collector._validate_hop("file:///etc/passwd", {"example.com"})


_TG_HTML = b"""<html><body><div class="tgme_channel_info"></div>
<div class="tgme_widget_message js-widget_message" data-post="osintchan/41">
  <div class="tgme_widget_message_text js-message_text">Leak site lists <b>Example Corp</b> victim<br/>IOC: evil-c2[.]example</div>
  <a class="tgme_widget_message_date"><time datetime="2026-10-20T08:00:00+00:00"></time></a>
</div>
<div class="tgme_widget_message js-widget_message" data-post="osintchan/42">
  <a class="tgme_widget_message_photo_wrap"></a>
  <a class="tgme_widget_message_date"><time datetime="2026-10-21T09:30:00+00:00"></time></a>
</div>
</body></html>"""


def test_parse_telegram_public_preview():
    from app.collector import parse_telegram, telegram_preview_url

    items = parse_telegram(_TG_HTML)
    assert [i["link"] for i in items] == ["https://t.me/osintchan/41", "https://t.me/osintchan/42"]
    assert items[0]["text"] == "[Telegram @osintchan]\nLeak site lists Example Corp victim\nIOC: evil-c2[.]example"
    assert items[1]["text"] == "[Telegram @osintchan] (fotoğraf)"
    assert items[0]["published"].isoformat() == "2026-10-20T08:00:00+00:00"
    assert telegram_preview_url("@osintchan") == "https://t.me/s/osintchan"
    assert telegram_preview_url("https://t.me/osintchan") == "https://t.me/s/osintchan"
    assert telegram_preview_url("https://evil.example/osintchan") is None


def test_dns_rebinding_peer_check_blocks_private_peer(no_dns, monkeypatch):
    # Doğrulamada genel bir IP'ye çözülen ad, bağlantı anında 127.0.0.1'e gitmiş olsun.
    class _Sock:
        def getpeername(self):
            return ("127.0.0.1", 443)

    resp = _FakeResponse()
    resp.raw = type("Raw", (), {"_connection": type("Conn", (), {"sock": _Sock()})()})()
    monkeypatch.setattr(collector, "_session", lambda: _FakeSession(resp))
    with pytest.raises(CollectorSecurityError, match="rebinding"):
        safe_fetch("https://example.com/x", {"example.com"})
