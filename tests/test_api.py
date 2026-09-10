import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from src.api import create_app
from src.simulation import observation

READ = "r" * 40
ADMIN = "a" * 40
SENSOR = "s" * 40


@pytest.fixture
def client(runtime, monkeypatch):
    monkeypatch.setenv("WILDLIFE_API_KEY", READ)
    monkeypatch.setenv("WILDLIFE_ADMIN_KEY", ADMIN)
    monkeypatch.setenv("WILDLIFE_SENSOR_KEYS", json.dumps({"demo/north": SENSOR}))
    with TestClient(create_app(runtime=runtime, background=False)) as c:
        yield c


def auth(key=READ):
    return {"Authorization": "Bearer " + key}


def test_read_auth_and_static_console(client):
    assert client.get("/healthz").status_code == 200
    assert client.get("/").status_code == 200
    assert "Wildlife Watch" in client.get("/").text
    assert client.get("/status").status_code == 401
    assert client.get("/status", headers=auth("wrong")).status_code == 403
    assert client.get("/status", headers=auth()).status_code == 200


def test_live_status_shared_with_ingest(client, clock):
    assert client.get("/readyz").status_code == 503
    payload = observation(clock, 1).model_dump(mode="json")
    assert client.post("/v1/observations", json=payload, headers=auth(SENSOR)).status_code == 200
    assert client.get("/readyz").status_code == 200
    assert client.get("/status", headers=auth()).json()["sites"][0]["monitoring_healthy"]


def test_sensor_and_read_keys_cannot_operate_hold(client):
    for key in (READ, SENSOR):
        assert (
            client.post(
                "/v1/sites/demo/hold", json={"enabled": True, "reason": "bench check"}, headers=auth(key)
            ).status_code
            == 403
        )
    assert (
        client.post(
            "/v1/sites/demo/hold", json={"enabled": True, "reason": "bench check"}, headers=auth(ADMIN)
        ).status_code
        == 200
    )
    assert client.get("/status", headers=auth()).json()["sites"][0]["manual_hold"]


def test_read_and_admin_keys_cannot_spoof_sensors(client, clock):
    payload = observation(clock, 1).model_dump(mode="json")
    for key in (READ, ADMIN):
        assert client.post("/v1/observations", json=payload, headers=auth(key)).status_code == 403
    payload["sensor_id"] = "other"
    assert client.post("/v1/observations", json=payload, headers=auth(SENSOR)).status_code == 403


def test_ingest_retry_and_replay_statuses(client, clock):
    obs = observation(clock, 1).model_dump(mode="json")
    assert client.post("/v1/observations", json=obs, headers=auth(SENSOR)).json()["accepted"]
    assert client.post("/v1/observations", json=obs, headers=auth(SENSOR)).json()["duplicate"]
    obs["observation_id"] = "other-id"
    assert client.post("/v1/observations", json=obs, headers=auth(SENSOR)).status_code == 409


@pytest.mark.parametrize(
    "path",
    [
        "/risk?lat=nan&lon=0",
        "/risk?lat=91&lon=0",
        "/risk?lat=0&lon=181",
        "/risk?lat=0&lon=0&at=2026-09-10T00:00:00",
        "/events?limit=10000",
        "/events?after=-1",
    ],
)
def test_query_validation(client, path):
    assert client.get(path, headers=auth()).status_code == 422


def test_oversize_payload(client):
    response = client.post("/v1/observations", content=b"x" * 65537, headers=auth(SENSOR))
    assert response.status_code == 413


def test_event_feed_hotspots_metrics(client):
    assert client.get("/hotspots", headers=auth()).json()["features"][0]["geometry"]["coordinates"] == [0, 0]
    feed = client.get("/events", headers=auth()).json()
    assert feed["events"][0]["physical_control"] is False
    assert "wildlife_monitoring_healthy" in client.get("/metrics", headers=auth()).text


def test_risk_outside_coverage_is_unknown(client):
    result = client.get("/risk?lat=50&lon=50", headers=auth()).json()
    assert result["risk"] is None
    assert result["coverage"] == "outside_configured_coverage"


def test_historical_risk_does_not_use_live_animals(client, clock, runtime):
    for i in range(2):
        clock.advance(0.2)
        runtime.ingest(observation(clock, i, label="deer"))
    at = datetime.fromtimestamp(clock.wall() - 86400, timezone.utc).isoformat()
    result = client.get("/risk", params={"lat": 0, "lon": 0, "at": at}, headers=auth()).json()
    assert "recent_confirmed_detection" not in result["corridors"][0]["factors"]
    assert not result["live_evidence_applied"]


def test_weak_or_shared_credentials_rejected(runtime, monkeypatch):
    monkeypatch.setenv("WILDLIFE_API_KEY", "weak")
    with pytest.raises(RuntimeError, match="32"):
        with TestClient(create_app(runtime=runtime)):
            pass
    monkeypatch.setenv("WILDLIFE_API_KEY", READ)
    monkeypatch.setenv("WILDLIFE_ADMIN_KEY", READ)
    with pytest.raises(RuntimeError, match="distinct"):
        with TestClient(create_app(runtime=runtime)):
            pass


def test_sensor_rate_limit_is_scoped_and_recovers(client, clock):
    payload = observation(clock, 1).model_dump(mode="json")
    for _ in range(60):
        assert client.post("/v1/observations", json=payload, headers=auth(SENSOR)).status_code == 200
    assert client.post("/v1/observations", json=payload, headers=auth(SENSOR)).status_code == 429
    clock.advance(1.1)
    payload = observation(clock, 2).model_dump(mode="json")
    assert client.post("/v1/observations", json=payload, headers=auth(SENSOR)).status_code == 200


def test_empty_optional_credentials_allow_read_only_service(runtime, monkeypatch):
    monkeypatch.setenv("WILDLIFE_API_KEY", READ)
    monkeypatch.setenv("WILDLIFE_ADMIN_KEY", "")
    monkeypatch.setenv("WILDLIFE_SENSOR_KEYS", "")
    with TestClient(create_app(runtime=runtime, background=False)) as client:
        assert client.get("/status", headers=auth()).status_code == 200
        assert (
            client.post(
                "/v1/sites/demo/hold", json={"enabled": True, "reason": "test"}, headers=auth()
            ).status_code
            == 403
        )
