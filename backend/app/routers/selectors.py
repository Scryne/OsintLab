"""Faz 29 — seçici katmanının API'si. Grafa yazma mantığı `app/pivot.py`de.

Seçici kimliği `tür:değer` biçiminde ve değer `/` içerebilir (URL), bu yüzden yol parametreleri
`:path` ile alınıyor ve kimliği takip eden sabit bir son ek (`/detail`) kullanılıyor."""
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app import pivot, selectorindex
from app.models_pivot import (
    EntitySelector,
    ExtractedSelector,
    Selector,
    SelectorCreate,
    SelectorDetail,
    SelectorDetectRequest,
    SelectorDetectResult,
    SelectorEntityLinkCreate,
    SelectorExtractRequest,
    SelectorKindCount,
    SelectorList,
    SelectorReindexResult,
    SelectorUpdate,
)

router = APIRouter(prefix="/selectors", tags=["selectors"])
entity_router = APIRouter(prefix="/entities", tags=["selectors"])
claim_router = APIRouter(prefix="/claims", tags=["selectors"])


@router.get("", response_model=SelectorList)
def list_selectors(
    kind: str | None = None,
    q: str | None = None,
    include_ignored: bool = False,
    sort: str = Query("sightings", pattern="^(sightings|recent|value)$"),
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    flag: str | None = Query(None, pattern="^kev$"),
) -> SelectorList:
    if kind and kind not in selectorindex.KINDS:
        raise HTTPException(status_code=422, detail=f"Bilinmeyen seçici türü: {kind}")
    from app.enrichment.engine import exploited_cves

    exploited = {row["id"] for row in exploited_cves(limit=100_000)}
    data = pivot.list_selectors(kind, q, include_ignored, sort, limit, offset,
                                only_ids=exploited if flag == "kev" else None)
    for item in data["items"]:
        # Satır başına işaret: şimdilik yalnızca "gerçekte sömürülüyor" (KEV'in son koşusu).
        item["flags"] = ["KEV"] if item["id"] in exploited else []
    return SelectorList(**data)


@router.get("/export")
def export(
    format: str = Query("csv", pattern="^(csv|stix)$"),
    kind: str | None = None,
    q: str | None = None,
    flag: str | None = Query(None, pattern="^kev$"),
):
    """Görünen listeyi (aynı filtrelerle) dışa aktarır: CSV ya da STIX 2.1 paketi. Yok sayılan
    (yanlış pozitif) seçiciler hiçbir zaman dışa aktarılmaz."""
    from fastapi.responses import Response

    from app import stixexport
    from app.enrichment.engine import exploited_cves

    if kind and kind not in selectorindex.KINDS:
        raise HTTPException(status_code=422, detail=f"Bilinmeyen seçici türü: {kind}")
    exploited = {row["id"] for row in exploited_cves(limit=100_000)}
    rows = pivot.list_selectors(kind, q, False, "value", 100_000, 0,
                                only_ids=exploited if flag == "kev" else None)["items"]
    rows = [r for r in rows if r["kind"] not in ("email", "coord")]
    flags = {r["id"]: ["KEV"] for r in rows if r["id"] in exploited}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    if format == "stix":
        body = stixexport.dumps(stixexport.stix_bundle(rows, flags=flags))
        return Response(body, media_type="application/stix+json;version=2.1",
                        headers={"Content-Disposition": f'attachment; filename="osintlab-selectors-{stamp}.json"'})
    return Response(stixexport.to_csv(rows, flags=flags), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="osintlab-selectors-{stamp}.csv"'})


@router.get("/kinds", response_model=list[SelectorKindCount])
def kinds() -> list[SelectorKindCount]:
    counts = {row["kind"]: row["count"] for row in pivot.kind_counts()}
    return [
        SelectorKindCount(kind=k, label=selectorindex.KIND_LABELS[k], count=counts.get(k, 0))
        for k in selectorindex.KINDS
    ]


@router.post("/detect", response_model=SelectorDetectResult)
def detect(payload: SelectorDetectRequest) -> SelectorDetectResult:
    """Tek bir değerin türü — hızlı pivot (Faz 33) ve elle ekleme formu bunu kullanır."""
    found = selectorindex.detect(payload.value)
    if found is None:
        return SelectorDetectResult(kind=None, value=None, label=None, id=None)
    kind, value = found
    sid = selectorindex.selector_id(kind, value)
    return SelectorDetectResult(
        kind=kind, value=value, label=selectorindex.KIND_LABELS[kind], id=sid,
        exists=pivot.get_selector(sid) is not None,
    )


@router.post("/extract", response_model=list[ExtractedSelector])
def extract(payload: SelectorExtractRequest) -> list[ExtractedSelector]:
    """Grafa YAZMADAN bir metindeki seçicileri gösterir (yapıştırılan rapor, advisory...)."""
    return [
        ExtractedSelector(
            id=s.id, kind=s.kind, label=selectorindex.KIND_LABELS[s.kind], value=s.value,
            context=s.context, defanged=s.defanged, occurrences=s.occurrences,
        )
        for s in selectorindex.extract_unique(payload.text)
    ]


@router.post("", response_model=Selector, status_code=201)
def create_selector(payload: SelectorCreate) -> Selector:
    found = selectorindex.detect(payload.value)
    if found is None:
        raise HTTPException(
            status_code=422,
            detail="Değerin türü tanınamadı. Desteklenen: alan adı, IP, URL, e-posta, MD5/SHA-1/SHA-256, "
            "CVE, ATT&CK tekniği (T1059), ASN (AS13335), Bitcoin/Ethereum adresi, koordinat (enlem, boylam).",
        )
    selector, _ = pivot.upsert_selector(*found, origin="manual", note=payload.note)
    return Selector(**selector)


@router.post("/reindex", response_model=SelectorReindexResult)
def reindex() -> SelectorReindexResult:
    """Bütün gözlem ve belge metinlerini yeniden tarar. İdempotent — tekrar çalıştırmak yeni
    kenar üretmez, yalnızca kural değişikliğinden sonra yeni yakalananları ekler."""
    return SelectorReindexResult(**pivot.reindex_all())


@router.get("/{selector_id:path}/detail", response_model=SelectorDetail)
def detail(selector_id: str) -> SelectorDetail:
    data = pivot.selector_detail(selector_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Seçici bulunamadı")
    return SelectorDetail(**data)


@router.post("/{selector_id:path}/watch-check")
def watch_check(selector_id: str) -> dict:
    """İzlenen bir seçicinin izleme modüllerini şimdi çalıştırır (24 saatlik aralığı beklemeden)."""
    from app.selectorwatch import WATCH_MODULES, check_selector

    sel = pivot.get_selector(selector_id)
    if sel is None:
        raise HTTPException(status_code=404, detail="Seçici bulunamadı")
    notices = check_selector(sel, force=True)
    return {"modules": list(WATCH_MODULES.get(sel["kind"], ())), "notices": notices}


@router.get("/{selector_id:path}/graph")
def graph(selector_id: str, depth: int = Query(2, ge=1, le=3)) -> dict:
    data = pivot.pivot_graph(selector_id, depth)
    if data is None:
        raise HTTPException(status_code=404, detail="Seçici bulunamadı")
    return data


@router.post("/{selector_id:path}/entities", status_code=201)
def link_entity(selector_id: str, payload: SelectorEntityLinkCreate) -> dict:
    if not pivot.link_entity(selector_id, payload.entity_id, payload.note):
        raise HTTPException(status_code=404, detail="Seçici ya da entity bulunamadı")
    return {"selector_id": selector_id, "entity_id": payload.entity_id}


@router.delete("/{selector_id:path}/entities/{entity_id}", status_code=204)
def unlink_entity(selector_id: str, entity_id: str) -> None:
    if not pivot.unlink_entity(selector_id, entity_id):
        raise HTTPException(status_code=404, detail="Bu seçici bu entity'ye bağlı değil")


@router.patch("/{selector_id:path}", response_model=Selector)
def update(selector_id: str, payload: SelectorUpdate) -> Selector:
    row = pivot.update_selector(selector_id, payload.status, payload.note)
    if row is None:
        raise HTTPException(status_code=404, detail="Seçici bulunamadı")
    return Selector(**row)


@claim_router.get("/{claim_id}/grade")
def claim_grade(claim_id: str) -> dict:
    """NATO/Admiralty kodu (ör. B2) — kaynağın güvenilirliği + claim'in doğrulama durumundan
    deterministik çeviri (bkz. `app/admiralty.py`)."""
    from app import admiralty
    from app.db import fetch_one, get_connection

    row = fetch_one(get_connection().execute(
        "MATCH (c:Claim {id: $id}) OPTIONAL MATCH (s:Source)-[:ASSERTS]->(c) "
        "RETURN c.knowledge_state AS state, s.reliability AS reliability",
        {"id": claim_id},
    ))
    if row is None:
        raise HTTPException(status_code=404, detail="Claim bulunamadı")
    return admiralty.code(row["reliability"], row["state"])


@claim_router.get("/{claim_id}/selectors", response_model=list[Selector])
def claim_selectors(claim_id: str) -> list[Selector]:
    return [Selector(**row) for row in pivot.claim_selectors(claim_id)]


@entity_router.get("/{entity_id}/selectors", response_model=list[EntitySelector])
def entity_selectors(entity_id: str) -> list[EntitySelector]:
    return [EntitySelector(**row) for row in pivot.entity_selectors(entity_id)]
