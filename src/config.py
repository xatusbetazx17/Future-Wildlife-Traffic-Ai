"""Versioned, fail-fast configuration for an isolated edge service."""

from pathlib import Path
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

import yaml
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StrictBool, StrictInt, model_validator
from pydantic import FiniteFloat as PydanticFiniteFloat


def require_number(value):
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError("expected a numeric value, not a string or boolean")
    return value


FiniteFloat = Annotated[PydanticFiniteFloat, BeforeValidator(require_number)]

Positive = Annotated[FiniteFloat, Field(gt=0)]
Identifier = Annotated[str, Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class TrafficConfig(Model):
    min_green_s: Positive = 8
    min_yellow_s: Positive = 3
    min_red_s: Positive = 6
    animal_crossing_hold_s: Positive = 15
    clear_s: Positive = 5
    max_crossing_s: Positive = 120


class SensorConfig(Model):
    id: Identifier
    kind: Literal["external", "camera", "video"] = "external"
    required: StrictBool = True
    source: str | StrictInt | None = None
    detector: Literal["yolo", "motion"] = "yolo"
    model_path: str | None = None
    model_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")] | None = None
    roi: list[list[Annotated[FiniteFloat, Field(ge=0, le=1)]]] = Field(
        default_factory=lambda: [[0, 0], [1, 0], [1, 1], [0, 1]], min_length=3, max_length=64
    )
    max_age_s: Positive = 3
    max_fps: Annotated[FiniteFloat, Field(gt=0, le=60)] = 5
    allowed_conditions: list[Literal["dry", "rain", "snow", "fog", "unknown"]] = Field(
        default_factory=lambda: ["dry"], min_length=1
    )

    @model_validator(mode="after")
    def validate_sensor(self):
        from .geometry import valid_polygon

        if not valid_polygon(self.roi):
            raise ValueError("roi must be a simple, nonzero-area polygon with distinct vertices")
        if self.kind != "external":
            if self.source is None or isinstance(self.source, bool):
                raise ValueError("camera/video sensors require a source")
            if self.kind == "video" and not isinstance(self.source, str):
                raise ValueError("video source must be a local path")
            if self.detector == "yolo" and not (self.model_path and self.model_sha256):
                raise ValueError("YOLO requires a local model_path and model_sha256")
        return self


class SiteConfig(Model):
    id: Identifier
    name: Annotated[str, Field(min_length=1, max_length=120)]
    latitude: Annotated[FiniteFloat, Field(ge=-90, le=90)]
    longitude: Annotated[FiniteFloat, Field(ge=-180, le=180)]
    timezone: str = "UTC"
    radius_m: Annotated[FiniteFloat, Field(gt=0, le=100000)] = 500
    species: list[Identifier] = Field(default_factory=lambda: ["deer"], min_length=1, max_length=100)
    confidence: Annotated[FiniteFloat, Field(gt=0, le=1)] = 0.7
    confirm_frames: Annotated[StrictInt, Field(ge=1, le=100)] = 3
    confirm_window_s: Positive = 2
    event_ttl_s: Annotated[FiniteFloat, Field(ge=2, le=3600)] = 30
    base_risk: Annotated[FiniteFloat, Field(ge=0, le=60)] = 20
    active_months: list[Annotated[StrictInt, Field(ge=1, le=12)]] = Field(default_factory=list)
    high_risk_hours: list[Annotated[StrictInt, Field(ge=0, le=23)]] = Field(default_factory=list)
    advisory_speed_kph: Annotated[FiniteFloat, Field(gt=0, le=130)] | None = None
    traffic: TrafficConfig = Field(default_factory=TrafficConfig)
    sensors: list[SensorConfig] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def validate_site(self):
        try:
            ZoneInfo(self.timezone)
        except (KeyError, ValueError) as exc:
            raise ValueError("timezone must be an IANA timezone") from exc
        if len({s.id for s in self.sensors}) != len(self.sensors):
            raise ValueError("sensor IDs must be unique within a site")
        if not any(s.required for s in self.sensors):
            raise ValueError("at least one sensor must be required")
        if len(set(self.species)) != len(self.species) or any(s != s.lower() for s in self.species):
            raise ValueError("species must be unique lowercase labels")
        return self


class MqttConfig(Model):
    enabled: StrictBool = False
    host: str = "localhost"
    port: Annotated[StrictInt, Field(ge=1, le=65535)] = 8883
    topic_prefix: Annotated[str, Field(pattern=r"^[a-zA-Z0-9/_-]{1,100}$")] = "wildlife/v1"
    ca_file: str | None = None
    cert_file: str | None = None
    key_file: str | None = None
    username_env: str | None = None
    password_env: str | None = None
    allow_insecure_localhost: StrictBool = False

    @model_validator(mode="after")
    def validate_tls(self):
        if self.enabled and not self.ca_file:
            if not (self.allow_insecure_localhost and self.host in {"localhost", "127.0.0.1", "::1"}):
                raise ValueError("MQTT requires a CA; only explicit loopback lab use can disable TLS")
        if bool(self.cert_file) != bool(self.key_file):
            raise ValueError("MQTT cert_file and key_file must be paired")
        if bool(self.username_env) != bool(self.password_env):
            raise ValueError("MQTT credential environment names must be paired")
        return self


class AppConfig(Model):
    schema_version: Literal[1] = 1
    mode: Literal["simulation", "shadow"] = "shadow"
    database_path: str = "var/wildlife.sqlite3"
    api_key_env: str = "WILDLIFE_API_KEY"
    admin_key_env: str = "WILDLIFE_ADMIN_KEY"
    sensor_keys_env: str = "WILDLIFE_SENSOR_KEYS"
    tick_s: Annotated[FiniteFloat, Field(gt=0, le=1)] = 0.25
    retention_days: Annotated[StrictInt, Field(ge=1, le=365)] = 7
    max_observations: Annotated[StrictInt, Field(ge=100, le=10000000)] = 100000
    max_events: Annotated[StrictInt, Field(ge=100, le=10000000)] = 100000
    sites: list[SiteConfig] = Field(min_length=1, max_length=100)
    mqtt: MqttConfig = Field(default_factory=MqttConfig)

    @model_validator(mode="after")
    def unique_sites(self):
        if len({s.id for s in self.sites}) != len(self.sites):
            raise ValueError("site IDs must be unique")
        if any(s.event_ttl_s <= self.tick_s * 4 for s in self.sites):
            raise ValueError("event TTL must exceed four heartbeat intervals")
        return self


def load_config(path: str | Path) -> AppConfig:
    path = Path(path).resolve()
    with path.open(encoding="utf-8") as f:
        cfg = AppConfig.model_validate(yaml.safe_load(f))

    def resolve(value):
        return str((path.parent / value).resolve()) if value else value

    cfg.database_path = resolve(cfg.database_path)
    for site in cfg.sites:
        for sensor in site.sensors:
            if sensor.kind == "video":
                sensor.source = resolve(sensor.source)
            sensor.model_path = resolve(sensor.model_path)
    # Assign paired TLS fields together so assignment validation stays valid.
    cfg.mqtt = cfg.mqtt.model_copy(
        update={field: resolve(getattr(cfg.mqtt, field)) for field in ("ca_file", "cert_file", "key_file")}
    )
    return cfg
