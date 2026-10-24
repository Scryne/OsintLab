"""Faz 29-35 — seçici, zenginleştirme ve pivot katmanının şemaları.

`app/models.py` 1.200 satırı geçti; yeni katman kendi dosyasında, aynı kalıplarla."""
from datetime import datetime

from pydantic import BaseModel, Field

from app.models import NonBlank


class Selector(BaseModel):
    id: str
    kind: str
    value: str
    status: str
    origin: str
    note: str | None = None
    created_at: datetime


class SelectorListItem(Selector):
    observation_count: int = 0
    evidence_count: int = 0
    enrichment_count: int = 0
    entity_count: int = 0
    first_seen: datetime | None = None
    last_seen: datetime | None = None


class SelectorList(BaseModel):
    total: int
    items: list[SelectorListItem]


class SelectorKindCount(BaseModel):
    kind: str
    label: str
    count: int


class SelectorCreate(BaseModel):
    value: NonBlank
    note: str = ""


class SelectorUpdate(BaseModel):
    status: str | None = Field(None, pattern="^(ACTIVE|IGNORED)$")
    note: str | None = None


class SelectorDetectRequest(BaseModel):
    value: str


class SelectorDetectResult(BaseModel):
    kind: str | None
    value: str | None
    label: str | None
    id: str | None
    exists: bool = False


class SelectorExtractRequest(BaseModel):
    text: str = Field(..., max_length=500_000)


class ExtractedSelector(BaseModel):
    id: str
    kind: str
    label: str
    value: str
    context: str
    defanged: bool
    occurrences: int


class SelectorSighting(BaseModel):
    observation_id: str
    source_url: str | None = None
    observed_at: datetime | None = None
    promoted: bool | None = None
    context: str | None = None
    defanged: bool | None = None
    occurrences: int | None = None
    claim_id: str | None = None
    claim_state: str | None = None


class SelectorDocument(BaseModel):
    evidence_id: str
    file_path: str | None = None
    evidence_type: str | None = None
    context: str | None = None
    defanged: bool | None = None
    occurrences: int | None = None


class SelectorEntityLink(BaseModel):
    id: str
    name: str
    entity_type: str
    note: str | None = None
    linked_at: datetime | None = None


class SelectorPivot(BaseModel):
    id: str
    kind: str
    value: str
    relation: str
    module: str | None = None
    run_id: str | None = None
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    direction: str


class SelectorCoOccurrence(BaseModel):
    id: str
    kind: str
    value: str
    shared: int


class SelectorDetail(BaseModel):
    selector: Selector
    label: str
    observation_count: int
    source_hosts: list[str]
    sightings: list[SelectorSighting]
    documents: list[SelectorDocument]
    entities: list[SelectorEntityLink]
    pivots: list[SelectorPivot]
    co_occurring: list[SelectorCoOccurrence]


class SelectorEntityLinkCreate(BaseModel):
    entity_id: str
    note: str = ""


class EntitySelector(Selector):
    link_note: str | None = None


class SelectorReindexResult(BaseModel):
    observations_scanned: int
    evidence_scanned: int
    new_sightings: int
    selectors_total: int
    orphans_removed: int = 0
    failed: int = 0
    duration_seconds: float
