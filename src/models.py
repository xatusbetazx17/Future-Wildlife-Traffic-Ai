from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import Field, StrictBool, model_validator

from .config import FiniteFloat, Identifier, Model


class Detection(Model):
    label: Identifier
    confidence: Annotated[FiniteFloat, Field(ge=0, le=1)]
    bbox: list[Annotated[FiniteFloat, Field(ge=0, le=1)]] = Field(min_length=4, max_length=4)
    evidence: Literal["classified", "motion"] = "classified"

    @model_validator(mode="after")
    def ordered_box(self):
        x1, y1, x2, y2 = self.bbox
        if x1 >= x2 or y1 >= y2:
            raise ValueError("bbox must have x1<x2 and y1<y2 in normalized coordinates")
        if self.label != self.label.lower():
            raise ValueError("label must be lowercase")
        return self


class Observation(Model):
    schema_version: Literal[1] = 1
    observation_id: Identifier
    site_id: Identifier
    sensor_id: Identifier
    observed_at: datetime
    healthy: StrictBool = True
    conditions: Literal["dry", "rain", "snow", "fog", "unknown"] = "unknown"
    detections: list[Detection] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validate_observation(self):
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must include UTC offset")
        if not self.healthy and self.detections:
            raise ValueError("unhealthy observations cannot assert detections")
        return self


class ManualHold(Model):
    enabled: StrictBool
    reason: Annotated[str, Field(min_length=3, max_length=200)]


class Location(Model):
    latitude: Annotated[FiniteFloat, Field(ge=-90, le=90)]
    longitude: Annotated[FiniteFloat, Field(ge=-180, le=180)]
    radius_m: Annotated[FiniteFloat, Field(gt=0)]


class Event(Model):
    schema_version: Literal[1] = 1
    event_id: Identifier
    site_id: Identifier
    issued_at: datetime
    expires_at: datetime
    type: Literal["wildlife_detected", "monitoring_unavailable", "operator_hold", "no_recent_detection"]
    species: list[Identifier]
    monitoring_healthy: StrictBool
    phase: Literal["RED", "GREEN", "YELLOW", "ANIMAL_CROSSING", "FAULT"]
    phase_is_simulated: Literal[True] = True
    mode: Literal["simulation", "shadow"]
    physical_control: Literal[False] = False
    location: Location
    advisory_speed_kph: Annotated[FiniteFloat, Field(gt=0, le=130)] | None
    message: Annotated[str, Field(min_length=1, max_length=500)]

    @model_validator(mode="after")
    def validity(self):
        if self.issued_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("event validity requires timezone offsets")
        if self.expires_at <= self.issued_at:
            raise ValueError("event must expire after issue time")
        return self


def utc_string(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()
