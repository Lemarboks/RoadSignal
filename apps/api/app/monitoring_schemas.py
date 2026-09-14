from datetime import datetime, timedelta, timezone
import json
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, FiniteFloat, HttpUrl, JsonValue, field_validator, model_validator


class MonitoringInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


DeviceId = Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9 _.-]+$")]
ReadingKey = Annotated[str, Field(min_length=1, max_length=48, pattern=r"^[a-zA-Z][a-zA-Z0-9_]*$")]


class DemoDevice(MonitoringInput):
    id: DeviceId
    kind: Literal["vehicle", "sensor"]
    label: str = Field(min_length=1, max_length=120)
    source: Literal["demo"]
    state: Literal["moving", "idle", "offline", "arrived", "reporting", "stale"]
    reported_at: AwareDatetime
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    readings: dict[ReadingKey, FiniteFloat | None] = Field(default_factory=dict, max_length=32)

    @model_validator(mode="after")
    def valid_device(self):
        states = {"moving", "idle", "offline", "arrived"} if self.kind == "vehicle" else {"reporting", "stale"}
        if self.state not in states:
            raise ValueError("Device state does not match device kind")
        if self.reported_at > datetime.now(timezone.utc) + timedelta(seconds=30):
            raise ValueError("Device timestamp cannot be in the future")
        return self


class TelemetryIngest(MonitoringInput):
    source: Literal["demo"]
    devices: list[DemoDevice] = Field(min_length=1, max_length=100)

    @field_validator("devices")
    @classmethod
    def unique_devices(cls, devices):
        if len({item.id for item in devices}) != len(devices):
            raise ValueError("Each device id must occur only once per batch")
        return devices


class AutomationRun(MonitoringInput):
    run_key: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.:-]+$")


class EvidencePassage(MonitoringInput):
    text: str = Field(min_length=8, max_length=8000)
    source_url: HttpUrl | None = None
    observed_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def safe_metadata(self):
        if self.source_url and (self.source_url.username or self.source_url.password):
            raise ValueError("Source URLs must not contain credentials")
        if self.observed_at and self.observed_at > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("Evidence observation time cannot be in the future")
        return self


class EvidenceSubmit(MonitoringInput):
    # Submission metadata is untrusted evidence, not a verified road incident.
    source: Literal["demo", "submitted"]
    event_id: str = Field(min_length=1, max_length=160)
    claim: str = Field(min_length=8, max_length=2000)
    evidence: list[EvidencePassage] = Field(min_length=1, max_length=20)
    analysis: dict[str, JsonValue] | None = Field(default=None, max_length=32)

    @field_validator("analysis")
    @classmethod
    def bounded_analysis(cls, value):
        if value is None:
            return value
        def depth(item, level=0):
            if level > 8:
                raise ValueError("Analysis must not exceed eight nesting levels")
            if isinstance(item, dict):
                if len(item) > 100 or any(len(key) > 128 for key in item):
                    raise ValueError("Analysis object is too large")
                for child in item.values():
                    depth(child, level + 1)
            elif isinstance(item, list):
                if len(item) > 100:
                    raise ValueError("Analysis list is too large")
                for child in item:
                    depth(child, level + 1)
        depth(value)
        if len(json.dumps(value, allow_nan=False)) > 64000:
            raise ValueError("Analysis is too large")
        return value

    @model_validator(mode="after")
    def provenance_required(self):
        if self.source == "submitted" and any(item.source_url is None for item in self.evidence):
            raise ValueError("Submitted evidence requires a source URL for every passage")
        return self


class EvidenceDecision(MonitoringInput):
    decision: Literal["approved", "rejected"]
    note: str = Field(min_length=3, max_length=2000)

    @field_validator("note")
    @classmethod
    def meaningful_note(cls, note):
        if len(note.strip()) < 3:
            raise ValueError("A review note is required")
        return note.strip()
