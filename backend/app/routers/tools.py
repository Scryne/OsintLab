"""Faz 32 — dış araç kataloğu ve arama operatörü tarifleri. Ağ isteği atmaz."""
from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app import solar, toolcatalog
from app.selectorindex import KINDS

router = APIRouter(prefix="/tools", tags=["tools"])
_KINDS = set(KINDS) | {"entity", "image_url"}


def _check(kind: str) -> None:
    if kind not in _KINDS:
        raise HTTPException(status_code=422, detail=f"Bilinmeyen tür: {kind}")


@router.get("")
def catalog() -> dict:
    return toolcatalog.catalog()


@router.get("/links")
def links(kind: str, value: str) -> list[dict]:
    _check(kind)
    return toolcatalog.links_for(kind, value)


@router.get("/dorks")
def dorks(kind: str, value: str) -> list[dict]:
    _check(kind)
    return toolcatalog.dorks_for(kind, value)


# --- Faz 34: güneş konumu ve kronolokasyon -------------------------------------------------

@router.get("/sun")
def sun(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    at: datetime | None = None,
    day: date | None = None,
) -> dict:
    """Verilen anda güneşin konumu ve gölge; ayrıca o günün 15 dakikalık tablosu."""
    when = (at or datetime.now(timezone.utc))
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    d = day or when.astimezone(timezone.utc).date()
    pos = solar.sun_position(lat, lon, when)
    return {
        "lat": lat, "lon": lon, "at_utc": when.astimezone(timezone.utc).isoformat(),
        "position": pos, "shadow": solar.shadow(pos["elevation"], pos["azimuth"]),
        "day": solar.day_table(lat, lon, datetime(d.year, d.month, d.day, tzinfo=timezone.utc)),
    }


class ChronolocateRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    day: date
    shadow_direction: float | None = Field(None, ge=0, lt=360)
    length_ratio: float | None = Field(None, gt=0, le=100)
    direction_tolerance: float = Field(5.0, gt=0, le=45)
    ratio_tolerance: float = Field(0.1, gt=0, le=1)


@router.post("/chronolocate")
def chronolocate(payload: ChronolocateRequest) -> dict:
    """Ölçülen gölge yönü (kuzeyden saat yönünde, derece) ve/veya gölge boyu / nesne boyu
    oranından, o gün o konumda bu geometrinin oluştuğu saat aralıkları (UTC)."""
    try:
        windows = solar.chronolocate(
            payload.lat, payload.lon, datetime(payload.day.year, payload.day.month, payload.day.day, tzinfo=timezone.utc),
            shadow_direction=payload.shadow_direction, length_ratio=payload.length_ratio,
            direction_tolerance=payload.direction_tolerance, ratio_tolerance=payload.ratio_tolerance,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"windows": windows[:10]}
