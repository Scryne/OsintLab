"""Faz 36 — altyapı izleme: izlenen bir seçicinin zenginleştirme sonuçlarındaki DEĞİŞİKLİK.

Faz 7'nin izleme mekanizması entity/olay/kaynak için vardı; profesyonel OSINT'te en sık izlenen
şey ise altyapıdır: bir alan adına yeni bir alt alan adı sertifikası çıktı mı, DNS'i başka bir
IP'ye döndü mü, kayıt şirketi değişti mi, bir IP'de yeni port açıldı mı, izlenen bir CVE KEV'e
girdi mi, bir cüzdan yaptırım listesine eklendi mi.

Kurallar:
- **Yalnızca kullanıcının izlemeye aldığı seçiciler** (Monitor target_type='Selector'). Sistem
  kendi başına bir şeyi izlemeye başlamaz.
- **Günde bir.** Her yeniden sorgu ilgini o servise yeniden gösterir (OPSEC) ve ücretsiz
  kotaları tüketir; altyapı değişiklikleri saatlik değil günlük ölçekte anlamlı.
- **Yalnızca pasif/yerel modüller.** Aktif bir modül izlemeye asla girmez.
- **Değişiklik deterministik bir fark.** İki ardışık başarılı koşunun özeti karşılaştırılır; ilk
  koşu "değişiklik" sayılmaz (taban çizgisi).
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timedelta, timezone

from app.db import DATA_ROOT, atomic_write_text, fetch_all, fetch_one, get_connection, graph_lock
from app.enrichment import engine
from app.enrichment.base import ACTIVE
from app.monitoring import notify_if_monitored

logger = logging.getLogger(__name__)

WATCH_INTERVAL = timedelta(hours=24)

WATCH_MODULES: dict[str, tuple[str, ...]] = {
    "domain": ("dns", "crtsh", "rdap"),
    "email": ("dns",),
    "ip": ("internetdb", "ripestat-ip", "ptr"),
    "asn": ("ripestat-asn",),
    "cve": ("kev", "epss"),
    "btc": ("sanctions-crypto",),
    "eth": ("sanctions-crypto",),
}

# Bu değişiklikler HIGH: "gerçekte sömürülüyor" ve "yaptırım listesine girdi" geri dönüşü olmayan,
# eyleme dönük olgular. Diğer her altyapı değişikliği MEDIUM.
ALERT_CODES = {"KEV_ADDED", "SANCTIONED"}


def _set(values) -> set:
    return set(values or [])


def diff(module: str, before: dict, after: dict) -> list[dict]:
    """[{code, text}] — boş liste "değişiklik yok"."""
    out: list[dict] = []

    def add(code: str, text: str) -> None:
        out.append({"code": code, "text": text})

    if module == "dns":
        b, a = before.get("records") or {}, after.get("records") or {}
        for rtype in sorted(set(b) | set(a)):
            added, removed = _set(a.get(rtype)) - _set(b.get(rtype)), _set(b.get(rtype)) - _set(a.get(rtype))
            if added:
                add("DNS_ADDED", f"{rtype} eklendi: {', '.join(sorted(added))}")
            if removed:
                add("DNS_REMOVED", f"{rtype} kalktı: {', '.join(sorted(removed))}")
        if bool(before.get("nxdomain")) != bool(after.get("nxdomain")):
            add("NXDOMAIN", "Alan adı artık çözülmüyor" if after.get("nxdomain") else "Alan adı yeniden çözülüyor")
    elif module == "crtsh":
        # İki koşu farklı kaynaktan geldiyse (crt.sh ↔ yedek Cert Spotter) karşılaştırılmaz: Cert
        # Spotter'ın anonim yanıtı çok daha küçük, geri dönüşte sahte "N yeni alt alan adı" çıkardı.
        if before.get("provider") != after.get("provider"):
            return out
        capped = (before.get("subdomain_count") or 0) > len(before.get("subdomains") or []) or \
            (after.get("subdomain_count") or 0) > len(after.get("subdomains") or [])
        new = _set(after.get("subdomains")) - _set(before.get("subdomains"))
        if capped:
            # Liste kesilmişse küme farkı yanıltıcı (sıralamada sona düşen yeni ad görünmez).
            grown = (after.get("subdomain_count") or 0) - (before.get("subdomain_count") or 0)
            if grown > 0:
                add("NEW_SUBDOMAIN", f"Alt alan adı sayısı arttı: {before.get('subdomain_count')} → {after.get('subdomain_count')}")
        elif new:
            shown = ", ".join(sorted(new)[:10])
            add("NEW_SUBDOMAIN", f"{len(new)} yeni alt alan adı sertifikası: {shown}{' …' if len(new) > 10 else ''}")
        elif (after.get("certificate_count") or 0) > (before.get("certificate_count") or 0):
            add("NEW_CERT", f"Yeni sertifika: {before.get('certificate_count')} → {after.get('certificate_count')}")
    elif module == "rdap":
        if before.get("registered") is not False and after.get("registered") is False:
            add("UNREGISTERED", "Alan adının kaydı düştü")
        elif before.get("registered") is False and after.get("registered") is not False:
            add("REREGISTERED", "Alan adı yeniden kaydedildi")
        if before.get("registrar") != after.get("registrar") and after.get("registered") is not False:
            add("REGISTRAR", f"Kayıt şirketi: {before.get('registrar')} → {after.get('registrar')}")
        if _set(before.get("nameservers")) != _set(after.get("nameservers")) and after.get("nameservers") is not None:
            add("NAMESERVERS", f"Ad sunucuları: {', '.join(sorted(_set(after.get('nameservers'))))}")
        be, ae = (before.get("events") or {}), (after.get("events") or {})
        if be.get("expiration") != ae.get("expiration") and ae.get("expiration"):
            add("EXPIRATION", f"Bitiş tarihi: {str(be.get('expiration'))[:10]} → {str(ae.get('expiration'))[:10]}")
        if _set(before.get("status")) != _set(after.get("status")) and after.get("status") is not None:
            add("STATUS", f"Kayıt durumu: {', '.join(after.get('status') or [])}")
    elif module == "internetdb":
        for key, label in (("ports", "port"), ("vulns", "açık"), ("hostnames", "ana makine adı")):
            added = _set(after.get(key)) - _set(before.get(key))
            removed = _set(before.get(key)) - _set(after.get(key))
            if added:
                add(f"{key.upper()}_ADDED", f"Yeni {label}: {', '.join(map(str, sorted(added)))}")
            if removed:
                add(f"{key.upper()}_REMOVED", f"Kapanan {label}: {', '.join(map(str, sorted(removed)))}")
    elif module == "ripestat-ip":
        ba = {a.get("asn") for a in before.get("asns") or []}
        aa = {a.get("asn") for a in after.get("asns") or []}
        if ba != aa:
            add("ASN_CHANGED", f"Duyuran ASN değişti: {sorted(ba)} → {sorted(aa)}")
        if before.get("prefix") != after.get("prefix"):
            add("PREFIX_CHANGED", f"Önek: {before.get('prefix')} → {after.get('prefix')}")
    elif module == "ptr":
        if _set(before.get("ptr")) != _set(after.get("ptr")):
            add("PTR_CHANGED", f"Ters DNS: {', '.join(after.get('ptr') or []) or 'yok'}")
    elif module == "ripestat-asn":
        b4, a4 = (before.get("prefix_count") or {}).get("ipv4", 0), (after.get("prefix_count") or {}).get("ipv4", 0)
        if b4 and abs(a4 - b4) / b4 >= 0.1:
            add("PREFIXES", f"Duyurulan IPv4 önek sayısı {b4} → {a4}")
    elif module == "kev":
        if not before.get("in_kev") and after.get("in_kev"):
            add("KEV_ADDED", f"CISA KEV'e eklendi ({after.get('date_added')}): artık gerçekte sömürülüyor")
    elif module == "epss":
        bp, ap = before.get("percentile") or 0, after.get("percentile") or 0
        if (bp < 0.9 <= ap) or (ap - bp) >= 0.1:
            add("EPSS_RISE", f"EPSS yüzdelik dilimi yükseldi: %{bp * 100:.0f} → %{ap * 100:.0f}")
    elif module == "sanctions-crypto":
        if not before.get("listed") and after.get("listed"):
            add("SANCTIONED", "Adres OFAC SDN listesine eklendi")
    return out


# İzleme durumu: (seçici, modül) başına son deneme zamanı ve son KARŞILAŞTIRILAN koşu.
#
# Taban çizgisi "en son başarılı koşu" olsaydı, kullanıcının aradaki elle koşusu (ya da toplu bir
# KEV turu) geçişi yutardı: KEV'e giriş elle koşuda görülür, izleme koşusu "değişiklik yok" der ve
# alarm hiç düşmezdi. Aralık da yalnızca başarılı koşulara bakınca, sürekli düşen bir modül
# (crt.sh 502) günde bir yerine her 10 dakikada bir yeniden sorgulanıyordu — OPSEC kuralına aykırı.
STATE_PATH = DATA_ROOT / "config" / "selector_watch.json"
_state_lock = threading.Lock()


def _load_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_state(state: dict) -> None:
    atomic_write_text(STATE_PATH, json.dumps(state, ensure_ascii=False, indent=1))


def _run_summary(run_id: str) -> dict | None:
    row = fetch_one(get_connection().execute(
        "MATCH (r:EnrichmentRun {id: $id}) WHERE r.status = 'DONE' RETURN r.summary AS summary", {"id": run_id}
    ))
    return json.loads(row["summary"]) if row and row["summary"] else None


def watched_selectors() -> list[dict]:
    return fetch_all(get_connection().execute(
        "MATCH (m:Monitor) WHERE m.active = true AND m.target_type = 'Selector' "
        "MATCH (s:Selector {id: m.target_id}) RETURN s.id AS id, s.kind AS kind, s.value AS value"
    ))


def check_selector(selector: dict, *, now: datetime | None = None, force: bool = False) -> list[dict]:
    """Bir seçicinin zamanı gelmiş izleme modüllerini çalıştırır, farkları Inbox'a bildirir.
    Döndürür: üretilen bildirimler."""
    now = now or datetime.now(timezone.utc)
    settings = engine.load_settings()
    notices = []
    for name in WATCH_MODULES.get(selector["kind"], ()):
        module = engine.REGISTRY.get(name)
        if module is None or module.opsec == ACTIVE or not engine.is_enabled(module, settings):
            continue
        key = f"{selector['id']}|{name}"
        with _state_lock:
            state = _load_state()
            entry = state.get(key, {})
            last = entry.get("last_attempt")
            if not force and last and now - datetime.fromisoformat(last) < WATCH_INTERVAL:
                continue
            entry["last_attempt"] = now.isoformat()
            state[key] = entry
            _save_state(state)
        try:
            run = engine.run(name, selector["id"], force=True, wait=True)
        except engine.EnrichmentError as exc:
            logger.warning("İzleme %s / %s çalıştırılamadı: %s", name, selector["id"], exc)
            continue
        if run["status"] != "DONE":
            continue  # başarısız koşu taban çizgisini değiştirmez ve fark üretmez
        baseline_id = entry.get("compared_run")
        with _state_lock:
            state = _load_state()
            state.setdefault(key, {})["compared_run"] = run["id"]
            state[key]["last_attempt"] = entry["last_attempt"]
            _save_state(state)
        baseline = _run_summary(baseline_id) if baseline_id else None
        if baseline is None:
            continue  # ilk başarılı izleme koşusu taban çizgisidir
        changes = diff(name, baseline, run["summary"] or {})
        if not changes:
            continue
        alert = any(c["code"] in ALERT_CODES for c in changes)
        title = f"{selector['value']} — {module.label}: " + "; ".join(c["text"] for c in changes[:2])
        with graph_lock:
            notice = notify_if_monitored(
                get_connection(),
                target_type="Selector",
                target_id=selector["id"],
                item_type="SELECTOR_ALERT" if alert else "SELECTOR_CHANGE",
                title=title[:300],
                detail={
                    "module": name,
                    "module_label": module.label,
                    "changes": changes,
                    "run_id": run["id"],
                    "previous_run_id": baseline_id,
                    # Aynı modülün aynı seçicideki bekleyen bildirimi güncellenir, çoğaltılmaz.
                    "subject_id": key,
                },
            )
        if notice:
            notices.append(notice)
    return notices


def run_due_watches() -> list[dict]:
    notices = []
    for selector in watched_selectors():
        try:
            notices.extend(check_selector(selector))
        except Exception:  # noqa: BLE001 — bir seçici diğerlerinin izlemesini düşürmemeli
            logger.exception("Seçici izleme turu çöktü: %s", selector["id"])
    return notices
