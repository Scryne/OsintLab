"""Faz 30 — zenginleştirme modüllerinin ortak yapı taşları.

Bir modül tek bir şey yapar: bir hedefi (seçici ya da entity) alır, bir ya da birkaç dış kaynağa
sorar ve yapılandırılmış bir özet + yeni seçicilere giden pivotlar döndürür. Ağ, kayıt ve graf
yazımı modülün işi DEĞİL — motorun (`engine.py`). Böylece her modül aynı güvencelerle çalışıyor:

- **Aynı SSRF katmanı.** Bütün istekler `collector.safe_fetch` üzerinden, modülün kendi sabit host
  listesiyle. Kullanıcının toplayıcı allowlist'i burada kullanılmaz: o, "hangi siteden içerik
  toplanır" kararı; bu ise kodun içinde sabit, bilinen API uçları.
- **Ham yanıt saklanır.** `Ctx` her yanıtı kaydeder; motor bunları diske yazıp SHA-256'sını alır.
  Özet bir yorumdur, ham yanıt kanıttır (Evidence First).
- **Kibar istemci.** Host başına asgari aralık (crt.sh, Nominatim, NVD, GDELT'in yazılı ya da
  ölçülmüş sınırları). Aşım cevabı (429) "kaynakta veri yok" ile karıştırılmaz.
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import urlencode, urlparse

from app.collector import CollectorFetchError, safe_fetch

PASSIVE = "PASSIVE"
ACTIVE = "ACTIVE"
LOCAL = "LOCAL"

OPSEC_LABELS = {
    PASSIVE: "Pasif — üçüncü taraf bir veritabanına sorulur, hedefin altyapısına dokunulmaz. Sorgu o servise araştırma ilgini gösterir.",
    ACTIVE: "Aktif — hedefin kendi sunucusuna doğrudan istek atılır. Hedef bunu loglarında görebilir.",
    LOCAL: "Yerel — yalnızca bilgisayarındaki veri setine bakılır, dışarı istek çıkmaz.",
}

# Host başına iki istek arasındaki asgari süre (sn). Kaynaklar: crt.sh 2023 duyurusu (5/dk),
# Nominatim kullanım politikası (1/sn), NVD anahtarsız sınır (5 istek / 30 sn), GDELT'te ölçülen 429.
HOST_INTERVALS = {
    "crt.sh": 12.0,
    "nominatim.openstreetmap.org": 1.1,
    "services.nvd.nist.gov": 6.5,
    "api.gdeltproject.org": 6.0,
    "web.archive.org": 2.0,
    "archive.org": 1.0,
    "urlscan.io": 2.0,
    "query.wikidata.org": 1.0,
    "api.adsb.lol": 1.0,
}
DEFAULT_INTERVAL = 0.25

_last_call: dict[str, float] = {}
_host_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _throttle(host: str) -> None:
    with _locks_guard:
        lock = _host_locks.setdefault(host, threading.Lock())
    with lock:
        wait = HOST_INTERVALS.get(host, DEFAULT_INTERVAL) - (time.monotonic() - _last_call.get(host, 0.0))
        if wait > 0:
            time.sleep(wait)
        _last_call[host] = time.monotonic()


class ModuleError(Exception):
    """Modülün kendi kararıyla verdiği, kullanıcıya olduğu gibi gösterilecek hata."""


@dataclass
class Pivot:
    """`direction="out"`: hedef → yeni seçici (alan adı `resolves_to` IP). `"in"`: yeni seçici →
    hedef (alt alan adı `subdomain_of` alan adı)."""
    relation: str
    kind: str
    value: str
    direction: str = "out"


@dataclass
class Result:
    summary: dict[str, Any]
    pivots: list[Pivot] = field(default_factory=list)
    # Ham yanıt yerine saklanacak özet kayıt (yerel veri setleri — 55 MB'lık ATT&CK dosyasının
    # tamamını her koşuda kopyalamak yerine eşleşen kayıt + veri setinin hash'i).
    raw_override: Any = None


@dataclass
class Target:
    type: str  # "selector" | "entity"
    id: str
    kind: str  # seçici türü ya da "entity"
    value: str  # seçici değeri ya da entity adı
    entity_type: str | None = None
    aliases: list[str] = field(default_factory=list)


class Ctx:
    """Bir koşunun ağ bağlamı: istekleri sınırlar ve ham yanıtları toplar."""

    def __init__(self, hosts: frozenset[str]):
        self.hosts = set(hosts)
        self.responses: list[dict[str, Any]] = []
        self.request_urls: list[str] = []

    def allow(self, *hosts: str) -> None:
        """Dinamik ama güvenilir bir kaynaktan gelen host'u (IANA RDAP bootstrap) izinli yap."""
        self.hosts.update(h.lower() for h in hosts if h)

    def get(self, url: str, params: dict[str, Any] | None = None, *, headers: dict[str, str] | None = None,
            max_bytes: int | None = None, max_seconds: float | None = None, timeout: float | None = None,
            record: bool = True) -> tuple[bytes, str]:
        if params:
            url = f"{url}{'&' if '?' in url else '?'}{urlencode(params, doseq=True)}"
        host = (urlparse(url).hostname or "").lower()
        _throttle(host)
        self.request_urls.append(url)
        try:
            final_url, content, content_type = safe_fetch(
                url, self.hosts, headers=headers, max_bytes=max_bytes, max_seconds=max_seconds, timeout=timeout
            )
        except CollectorFetchError as exc:
            if exc.status_code == 429:
                raise ModuleError(f"{host} istek kotası doldu (429) — biraz sonra tekrar dene.") from exc
            raise
        if record:
            self.responses.append({
                "url": final_url,
                "content_type": content_type,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "body": _decode_for_record(content, content_type),
            })
        return content, content_type

    def get_json(self, url: str, params: dict[str, Any] | None = None, **kwargs) -> Any:
        # Toplayıcının varsayılan `Accept`i RSS'i öne alıyor; FIRST EPSS buna 400 döndürüyor
        # (2026-10-24'te ölçüldü). JSON uçlarına JSON istendiği açıkça söylenir.
        kwargs["headers"] = {"Accept": "application/json", **(kwargs.get("headers") or {})}
        content, _ = self.get(url, params, **kwargs)
        try:
            return json.loads(content.decode("utf-8", errors="replace"))
        except ValueError as exc:
            raise ModuleError(f"{urlparse(url).hostname} JSON olmayan bir yanıt döndürdü.") from exc


def _decode_for_record(content: bytes, content_type: str) -> Any:
    text = content.decode("utf-8", errors="replace")
    if "json" in content_type or text[:1] in "[{":
        try:
            return json.loads(text)
        except ValueError:
            pass
    return text[:200_000]


@dataclass
class Module:
    name: str
    label: str
    provider: str
    description: str
    target: str  # "selector" | "entity"
    kinds: tuple[str, ...]
    opsec: str
    hosts: frozenset[str]
    run: Callable[[Ctx, Target], Result]
    cache_hours: float = 24.0
    docs_url: str = ""
    terms_note: str = ""
    datasets: tuple[str, ...] = ()

    def accepts(self, target: Target) -> bool:
        if self.target != target.type:
            return False
        return target.type == "entity" or target.kind in self.kinds
