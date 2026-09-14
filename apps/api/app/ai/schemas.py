from typing import Literal

from pydantic import Field, field_validator, model_validator

from ..schemas import StrictModel, plain_text

IncidentType = Literal[
    "Accident", "Robbery", "Broken traffic light", "Road obstruction", "Pothole", "Flooding", "Other"
]


class IncidentAnalysisRequest(StrictModel):
    text: str = Field(min_length=5, max_length=1000)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @field_validator("text")
    @classmethod
    def clean_text(cls, value: str) -> str:
        value = plain_text(value)
        if len(value) < 5:
            raise ValueError("Describe the incident in at least five characters")
        return value

    @model_validator(mode="after")
    def coordinate_pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Provide both latitude and longitude")
        return self


class IncidentClassification(StrictModel):
    incident_type: IncidentType
    severity: int = Field(ge=1, le=5, strict=True)


class IncidentDraft(IncidentClassification):
    description: str = Field(max_length=1000)


class DuplicateCandidate(StrictModel):
    id: str
    incident_type: str
    description: str
    distance_km: float
    similarity: float = Field(ge=0, le=1)
    occurred_at: str


class IncidentAnalysisResponse(StrictModel):
    mode: Literal["model", "fallback"]
    retrieval_mode: Literal["semantic", "lexical", "unavailable"]
    draft: IncidentDraft
    duplicates: list[DuplicateCandidate]
    warnings: list[str]
    requires_review: Literal[True] = True


class EvidenceSelection(StrictModel):
    evidence_ids: list[str] = Field(min_length=1, max_length=4)


class RouteEvidence(StrictModel):
    id: str
    label: str
    value: str


class RouteExplanation(StrictModel):
    mode: Literal["model", "fallback"]
    summary: str
    evidence: list[RouteEvidence]
    warnings: list[str]
    score_unchanged: Literal[True] = True
