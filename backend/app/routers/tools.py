"""Faz 32 — dış araç kataloğu ve arama operatörü tarifleri. Ağ isteği atmaz."""
from fastapi import APIRouter, HTTPException

from app import toolcatalog
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
