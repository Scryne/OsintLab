from fastapi import APIRouter, HTTPException

from app.collector import (
    CollectorSecurityError,
    extract_text_from_html,
    load_allowlist,
    parse_rss,
    safe_fetch,
    save_allowlist,
)
from app.models import AllowlistAdd, CollectorFetchRequest, Observation
from app.routers.observations import create_observation_record

router = APIRouter(prefix="/collectors", tags=["collectors"])


@router.get("/allowlist")
def get_allowlist() -> dict:
    return {"hostnames": sorted(load_allowlist())}


@router.post("/allowlist", status_code=201)
def add_to_allowlist(payload: AllowlistAdd) -> dict:
    hosts = load_allowlist()
    hosts.add(payload.hostname)
    save_allowlist(hosts)
    return {"hostnames": sorted(hosts)}


@router.delete("/allowlist/{hostname}", status_code=204)
def remove_from_allowlist(hostname: str) -> None:
    hosts = load_allowlist()
    hosts.discard(hostname)
    save_allowlist(hosts)


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
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    created: list[Observation] = []

    if payload.mode == "rss":
        items = parse_rss(content)
        for item in items:
            created.append(
                create_observation_record(
                    raw_content=item["text"],
                    source_url=item["link"] or final_url,
                )
            )
    else:
        text = extract_text_from_html(content)
        created.append(create_observation_record(raw_content=text, source_url=final_url))

    return {
        "final_url": final_url,
        "content_type": content_type,
        "observations_created": len(created),
        "observation_ids": [o.id for o in created],
    }
