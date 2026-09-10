import hashlib
import sys
import types
from datetime import datetime

import numpy as np
import pytest
from pydantic import ValidationError

from src.config import AppConfig, MqttConfig, SensorConfig, load_config
from src.detection import AnimalDetector
from src.geometry import distance_m, inside
from src.health_check import HealthChecker
from src.models import Detection, Observation
from src.simulation import demo_config


@pytest.mark.parametrize("value", [True, "5", -1, 0, float("nan"), float("inf")])
def test_invalid_config_numeric(value):
    raw = demo_config().model_dump()
    raw["sites"][0]["traffic"]["min_yellow_s"] = value
    with pytest.raises(ValidationError):
        AppConfig.model_validate(raw)


def test_unknown_configuration_and_actuation_fields_rejected():
    for key, value in [("enable_physical_outputs", True), ("mode", "live"), ("schema_version", 2)]:
        raw = demo_config().model_dump()
        raw[key] = value
        with pytest.raises(ValidationError):
            AppConfig.model_validate(raw)


@pytest.mark.parametrize(
    "roi",
    [
        [[0, 0], [1, 1], [0, 1], [1, 0]],
        [[0, 0], [1, 0], [1, 0]],
        [[0, 0], [0.5, 0], [1, 0]],
        [[0, 0, 1], [1, 0], [0, 1]],
    ],
)
def test_malformed_roi_rejected(roi):
    with pytest.raises(ValidationError):
        SensorConfig(id="sensor", roi=roi)


def test_tls_required_for_nonlocal_mqtt():
    with pytest.raises(ValidationError):
        MqttConfig(enabled=True, host="broker.example.com")
    with pytest.raises(ValidationError):
        MqttConfig(enabled=True, host="broker.example.com", allow_insecure_localhost=True)
    assert MqttConfig(enabled=True, host="localhost", allow_insecure_localhost=True)


def test_paths_resolve_relative_to_config(tmp_path, monkeypatch):
    cfg = tmp_path / "pilot.yaml"
    cfg.write_text(
        "sites:\n- id: one\n  name: One\n  latitude: 0\n  longitude: 0\n  sensors:\n  - id: sensor\ndatabase_path: journal/db.sqlite3\n"
    )
    monkeypatch.chdir("/")
    assert load_config(cfg).database_path == str(tmp_path / "journal/db.sqlite3")


def test_roi_boundary_and_distance():
    assert inside((0, 0), [[0, 0], [1, 0], [1, 1], [0, 1]])
    assert not inside((2, 2), [[0, 0], [1, 0], [1, 1], [0, 1]])
    assert distance_m(0, 179.999, 0, -179.999) < 230


def test_motion_never_identifies_wildlife():
    detector = AnimalDetector(None, 0.7, ["deer"], backend="motion")
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    for _ in range(25):
        detector.detect(frame)
    frame[40:200, 50:200] = 255
    detections = detector.detect(frame)
    assert detections
    assert all(
        d.evidence == "motion" and d.label == "unknown_motion" and d.confidence == 0 for d in detections
    )
    with pytest.raises(ValueError):
        detector.detect(None)


def test_missing_model_or_hash_fails_closed(tmp_path):
    with pytest.raises(ValueError, match="local"):
        AnimalDetector(str(tmp_path / "absent.pt"), 0.7, ["deer"], "0" * 64)
    model = tmp_path / "untrusted.pt"
    model.write_bytes(b"not a real model")
    with pytest.raises(ValueError, match="SHA"):
        AnimalDetector(str(model), 0.7, ["deer"], "0" * 64)


def test_unsupported_species_rejected_before_inference(tmp_path, monkeypatch):
    model = tmp_path / "contract-fixture.pt"
    model.write_bytes(b"contract fixture")
    monkeypatch.setitem(
        sys.modules,
        "ultralytics",
        types.SimpleNamespace(YOLO=lambda path: types.SimpleNamespace(names={0: "bear"})),
    )
    with pytest.raises(ValueError, match="deer"):
        AnimalDetector(str(model), 0.7, ["deer"], hashlib.sha256(model.read_bytes()).hexdigest())


def test_no_invented_health_data():
    report = HealthChecker().check()
    assert report.surface_temperature_c is None and not report.diagnostic
    assert (
        HealthChecker().check(surface_temperature_c=35.0, source="calibrated-sensor").surface_temperature_c
        == 35
    )
    with pytest.raises(ValueError):
        HealthChecker().check(surface_temperature_c=40)


@pytest.mark.parametrize("bbox", [[0.5, 0, 0.2, 1], [0, 0, 2, 1], [0, 0, 0, 1], [0, 0, float("nan"), 1]])
def test_invalid_detection_bbox(bbox):
    with pytest.raises(ValidationError):
        Detection(label="deer", confidence=0.9, bbox=bbox)


def test_naive_timestamp_and_unhealthy_detections_rejected():
    with pytest.raises(ValidationError):
        Observation(observation_id="one", site_id="demo", sensor_id="north", observed_at=datetime(2026, 1, 1))
    with pytest.raises(ValidationError):
        Observation(
            observation_id="one",
            site_id="demo",
            sensor_id="north",
            observed_at="2026-01-01T00:00:00Z",
            healthy=False,
            detections=[{"label": "deer", "confidence": 0.9, "bbox": [0, 0, 1, 1]}],
        )
