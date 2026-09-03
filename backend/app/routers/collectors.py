from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException

from app.collector import (
    CollectorFetchError,
    CollectorSecurityError,
    extract_text_from_html,
    load_allowlist,
    normalize_hostname,
    parse_rss,
    safe_fetch,
    save_allowlist,
)
from app.db import fetch_all, get_connection
from app.models import AllowlistAdd, CollectorFetchRequest, Observation
from app.routers.observations import create_observation_record

router = APIRouter(prefix="/collectors", tags=["collectors"])


@router.get("/allowlist")
def get_allowlist() -> dict:
    return {"hostnames": sorted(load_allowlist())}


@router.post("/allowlist", status_code=201)
def add_to_allowlist(payload: AllowlistAdd) -> dict:
    hosts = load_allowlist()
    hostname = normalize_hostname(payload.hostname)
    if not hostname:
        raise HTTPException(status_code=422, detail="Geçerli bir hostname değil")
    hosts.add(hostname)
    save_allowlist(hosts)
    return {"hostnames": sorted(hosts)}


@router.delete("/allowlist/{hostname}", status_code=204)
def remove_from_allowlist(hostname: str) -> None:
    hosts = load_allowlist()
    hosts.discard(hostname)
    save_allowlist(hosts)


def _select_items(items: list[dict], *, limit: int, since_days: int | None) -> list[dict]:
    """Faz 11 (F2): feed'in tamamı yerine en yeni `limit` item, opsiyonel zaman penceresiyle.

    Yayın tarihi olmayan item'lar pencere filtresinde ELENMEZ (tarihsiz diye bilgi kaybetmeyi
    tarih uydurmaya tercih ediyoruz), ama sıralamada en sona düşerler."""
    if since_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
        items = [i for i in items if i["published"] is None or i["published"] >= cutoff]
    oldest = datetime.min.replace(tzinfo=timezone.utc)
    items = sorted(items, key=lambda i: i["published"] or oldest, reverse=True)
    return items[:limit]


def _existing_pairs(urls: list[str]) -> set[tuple[str, str]]:
    """Faz 11 (F3): daha önce aynı URL'den aynı içerikle gelmiş observation'ların kümesi.

    Dedup anahtarı bilerek (source_url, raw_content) — sadece URL olsaydı Faz 7'nin change
    detection'ı kırılırdı: aynı sayfa değişmiş içerikle yeniden tarandığında yeni bir
    observation oluşması GEREKİYOR. Değişmemişse oluşmamalı."""
    unique = sorted({u for u in urls if u})
    if not unique:
        return set()
    rows = fetch_all(
        get_connection().execute(
            "MATCH (o:Observation) WHERE o.source_url IN $urls "
            "RETURN o.source_url AS source_url, o.raw_content AS raw_content",
            {"urls": unique},
        )
    )
    return {(r["source_url"], r["raw_content"]) for r in rows}


@router.post("/fetch")
def fetch(payload: CollectorFetchRequest) -> dict:
    """Q22: allowlist + SSRF doğrulamasından geçen bir URL'i güvenli şekilde çeker, her
    öğeyi (rss) veya sayfanın tamamını (web) bir Observation olarak sisteme sokar. Toplanan
    içerik hiçbir şekilde yorumlanmaz/çalıştırılmaz — düz metin olarak saklanır."""
    if payload.mode not in ("rss", "web"):
        raise HTTPException(status_code=422, detail="mode must be 'rss' or 'web'")

    allowlist = load_allowlist()
    try:
        final_url, content, content_type = safe_fetch(payload.url, allowlist)
    except CollectorSecurityError as exc:
        # 403: BİZ reddettik (allowlist/SSRF) — kullanıcının düzeltebileceği bir yapılandırma.
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except CollectorFetchError as exc:
        # 502: KARŞI TARAF reddetti — bizim yapılandırmamızda bir sorun yok (F25).
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if payload.mode == "rss":
        parsed_items = parse_rss(content)
        available = len(parsed_items)
        # Faz 11 (F25, ikinci savunma): 200 döndüren ama feed olmayan bir yanıt da sessiz
        # sıfıra yol açar (ör. giriş/onay sayfası, "moved" HTML'i). Gerçekten boş bir feed
        # XML content-type'la gelir; HTML gelip 0 item çıkıyorsa bu boşluk değil, yanlış
        # içeriktir — ayırt edip söylüyoruz.
        if available == 0 and "xml" not in content_type.lower():
            raise HTTPException(
                status_code=502,
                detail=(
                    f"Yanıt bir feed değil: {content_type or 'tür belirtilmemiş'} döndü ve hiç "
                    f"öğe ayrıştırılamadı ({final_url}). Adres bir RSS/Atom feed'i mi, yoksa "
                    "normal bir sayfa mı? Sayfaysa 'web' modunu dene."
                ),
            )
        selected = _select_items(parsed_items, limit=payload.limit, since_days=payload.since_days)
        candidates = [
            {"text": i["text"], "url": i["link"] or final_url, "published": i["published"]}
            for i in selected
        ]
    else:
        available = 1
        candidates = [
            {"text": extract_text_from_html(content), "url": final_url, "published": None}
        ]

    seen = _existing_pairs([c["url"] for c in candidates])
    created: list[Observation] = []
    skipped = 0
    for c in candidates:
        key = (c["url"], c["text"])
        if key in seen:
            skipped += 1
            continue
        created.append(
            create_observation_record(
                raw_content=c["text"],
                observed_at=c["published"],
                source_url=c["url"],
            )
        )
        seen.add(key)

    return {
        "final_url": final_url,
        "content_type": content_type,
        "items_available": available,
        "items_considered": len(candidates),
        "observations_created": len(created),
        "duplicates_skipped": skipped,
        "observation_ids": [o.id for o in created],
    }
