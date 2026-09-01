from datetime import datetime

from pydantic import BaseModel, Field


class EntityCreate(BaseModel):
    entity_type: str = Field(..., examples=["Person", "Organization", "Company", "Location"])
    name: str
    aliases: list[str] = Field(default_factory=list)


class Entity(EntityCreate):
    id: str
    created_at: datetime


class EventCreate(BaseModel):
    title: str
    event_type: str = Field(..., examples=["saldırı", "seçim", "açıklama", "satın alma"])
    occurred_at: datetime | None = None
    location: str | None = None


class Event(EventCreate):
    id: str
    knowledge_state: str
    confidence: float
    created_at: datetime


class SourceCreate(BaseModel):
    name: str
    source_type: str = Field(..., examples=["haber sitesi", "resmi açıklama", "sosyal medya"])
    url: str | None = None
    reliability: float = Field(0.5, ge=0.0, le=1.0)


class Source(SourceCreate):
    id: str
    created_at: datetime


class EvidenceCreate(BaseModel):
    evidence_type: str = Field(..., examples=["fotoğraf", "video", "belge", "uydu görüntüsü"])
    file_path: str | None = None
    content_hash: str | None = None
    collected_at: datetime | None = None


class Evidence(EvidenceCreate):
    id: str
    created_at: datetime


class ClaimCreate(BaseModel):
    text: str
    source_id: str
    about_entity_id: str | None = None
    about_event_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    corroborates: list[str] = Field(
        default_factory=list, description="Bu claim'in bağımsız olarak doğruladığı diğer claim id'leri (Q4 corroboration girdisi)"
    )
    contradicts: list[str] = Field(
        default_factory=list, description="Bu claim'in çeliştiği diğer claim id'leri (Q9 Contradiction)"
    )
    supersedes: str | None = Field(
        None, description="Bu claim'in temporal olarak yerini aldığı eski claim id'si (Q9 temporal versiyonlama)"
    )


class Claim(BaseModel):
    id: str
    text: str
    source_id: str
    knowledge_state: str
    confidence: float
    valid_from: datetime
    valid_to: datetime | None
    created_at: datetime


class ObservationCreate(BaseModel):
    raw_content: str
    observed_at: datetime | None = None


class Observation(ObservationCreate):
    id: str
    promoted: bool
    created_at: datetime


INVESTIGATION_STATUSES = ("OPEN", "ACTIVE", "PAUSED", "RESOLVED", "CLOSED", "ARCHIVED")

# Q16 durum makinesi. ARCHIVED terminaldir (v1'de yeniden açılmaz).
INVESTIGATION_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "OPEN": ("ACTIVE", "ARCHIVED"),
    "ACTIVE": ("PAUSED", "RESOLVED", "ARCHIVED"),
    "PAUSED": ("ACTIVE", "ARCHIVED"),
    "RESOLVED": ("ACTIVE", "CLOSED", "ARCHIVED"),
    "CLOSED": ("ARCHIVED",),
    "ARCHIVED": (),
}


class InvestigationCreate(BaseModel):
    title: str
    research_question: str


class Investigation(InvestigationCreate):
    id: str
    status: str
    created_at: datetime


class InvestigationTransition(BaseModel):
    to_status: str = Field(..., examples=list(INVESTIGATION_STATUSES))


class HypothesisCreate(BaseModel):
    text: str = Field(..., examples=["H1: Company X is directly controlled by Organization Y."])


class Hypothesis(HypothesisCreate):
    id: str
    status: str
    created_at: datetime


class HypothesisEvidenceLink(BaseModel):
    evidence_id: str
    stance: str = Field(..., examples=["SUPPORTS", "WEAKENS", "REFUTES"])


class ObservationPromote(BaseModel):
    source_id: str
    about_entity_id: str | None = None
    about_event_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    corroborates: list[str] = Field(default_factory=list)
