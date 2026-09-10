from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest

from src.models import Detection
from src.runtime import Runtime
from src.simulation import demo_config, observation


def status(rt):
    return rt.status()["sites"][0]


def send(rt, clock, i, **kwargs):
    clock.advance(0.2)
    return rt.ingest(observation(clock, i, **kwargs))


def test_startup_unknown_then_clear(runtime, clock):
    assert not status(runtime)["monitoring_healthy"]
    send(runtime, clock, 1)
    assert status(runtime)["monitoring_healthy"]
    assert not status(runtime)["animal_detected"]


def test_species_confidence_roi_and_motion_filters(runtime, clock):
    for i, label in enumerate(["person", "cat", "bear"]):
        send(runtime, clock, i, label=label)
    assert not status(runtime)["animal_detected"]
    for i in range(3, 6):
        send(runtime, clock, i, label="deer", evidence="motion")
    assert not status(runtime)["animal_detected"]
    for i in range(6, 8):
        clock.advance(0.2)
        obs = observation(clock, i, label="deer")
        obs.detections[0].confidence = 0.1
        runtime.ingest(obs)
    assert not status(runtime)["animal_detected"]


def test_roi_excludes_boxes(clock):
    cfg = demo_config()
    cfg.sites[0].sensors[0].roi = [[0, 0], [0.4, 0], [0.4, 1], [0, 1]]
    rt = Runtime(cfg, clock.monotonic, clock.wall)
    try:
        for i in range(2):
            clock.advance(0.2)
            obs = observation(clock, i, label="deer")
            obs.detections = [Detection(label="deer", confidence=0.9, bbox=[0.6, 0.2, 0.9, 0.8])]
            rt.ingest(obs)
        assert not status(rt)["animal_detected"]
    finally:
        rt.close()


def test_debounce_and_gap_reset(runtime, clock):
    send(runtime, clock, 1, label="deer")
    assert not status(runtime)["animal_detected"]
    clock.advance(3)
    send(runtime, clock, 2, label="deer")
    assert not status(runtime)["animal_detected"]
    send(runtime, clock, 3, label="deer")
    assert status(runtime)["animal_detected"]


def test_species_frames_do_not_confirm_each_other(clock):
    cfg = demo_config()
    cfg.sites[0].species = ["deer", "bear"]
    rt = Runtime(cfg, clock.monotonic, clock.wall)
    try:
        send(rt, clock, 1, label="deer")
        send(rt, clock, 2, label="bear")
        assert not status(rt)["animal_detected"]
    finally:
        rt.close()


def test_duplicate_does_not_refresh_or_confirm(runtime, clock):
    obs = observation(clock, 1, label="deer")
    runtime.ingest(obs)
    clock.advance(0.5)
    assert runtime.ingest(obs) == {"accepted": False, "duplicate": True}
    assert not status(runtime)["animal_detected"]
    clock.advance(2)
    assert not status(runtime)["monitoring_healthy"]


def test_concurrent_duplicate_is_accepted_once(runtime, clock):
    obs = observation(clock, 1)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: runtime.ingest(obs), range(20)))
    assert sum(r["accepted"] for r in results) == 1


def test_reused_id_with_different_payload_is_rejected(runtime, clock):
    runtime.ingest(observation(clock, 1))
    clock.advance(0.1)
    with pytest.raises(ValueError, match="reused"):
        runtime.ingest(observation(clock, 1, label="deer"))


@pytest.mark.parametrize("offset", [-3, 2])
def test_stale_and_future_observations_rejected(runtime, clock, offset):
    obs = observation(clock, 1)
    obs.observed_at += timedelta(seconds=offset)
    with pytest.raises(ValueError):
        runtime.ingest(obs)
    assert runtime.observations_accepted == 0


def test_capture_timestamp_controls_freshness(runtime, clock):
    obs = observation(clock, 1)
    clock.advance(1.9)
    runtime.ingest(obs)
    clock.advance(0.2)
    assert not status(runtime)["monitoring_healthy"]


def test_out_of_order_rejected(runtime, clock):
    old = observation(clock, 1)
    send(runtime, clock, 2)
    with pytest.raises(ValueError, match="out-of-order"):
        runtime.ingest(old)


def test_weather_outside_envelope_is_fault(runtime, clock):
    send(runtime, clock, 1, conditions="fog")
    assert not status(runtime)["monitoring_healthy"]
    send(runtime, clock, 2, conditions="dry")
    assert status(runtime)["monitoring_healthy"]


def test_missing_required_peer_is_not_covered_by_other_sensor(clock):
    raw = demo_config().model_dump()
    raw["sites"][0]["sensors"].append({"id": "south"})
    from src.config import AppConfig

    rt = Runtime(AppConfig.model_validate(raw), clock.monotonic, clock.wall)
    try:
        send(rt, clock, 1, label="deer")
        send(rt, clock, 2, label="deer")
        assert status(rt)["animal_detected"]
        assert not status(rt)["monitoring_healthy"]
        assert status(rt)["required_sensor_faults"] == ["south"]
    finally:
        rt.close()


def test_multisite_isolation(clock):
    raw = demo_config().model_dump()
    raw["sites"].append(dict(raw["sites"][0], id="other"))
    from src.config import AppConfig

    rt = Runtime(AppConfig.model_validate(raw), clock.monotonic, clock.wall)
    try:
        send(rt, clock, 1, label="deer")
        send(rt, clock, 2, label="deer")
        data = rt.status()["sites"]
        assert data[0]["animal_detected"]
        assert not data[1]["animal_detected"]
        assert not data[1]["monitoring_healthy"]
    finally:
        rt.close()


def test_events_expire_and_cursors_advance(runtime, clock):
    send(runtime, clock, 1, label="deer")
    send(runtime, clock, 2, label="deer")
    events = runtime.store.events(clock.wall(), active_only=True)
    assert any(e["type"] == "wildlife_detected" for e in events)
    cursor = events[-1]["sequence"]
    assert not runtime.store.events(clock.wall(), after=cursor)
    clock.advance(100)
    assert not runtime.store.events(clock.wall(), active_only=True)


def test_manual_hold_and_watermark_survive_restart(clock, tmp_path):
    cfg = demo_config(str(tmp_path / "state.sqlite3"))
    rt = Runtime(cfg, clock.monotonic, clock.wall)
    obs = observation(clock, 1)
    rt.ingest(obs)
    rt.set_hold("demo", True, "maintenance")
    rt.close()
    rt = Runtime(cfg, clock.monotonic, clock.wall)
    try:
        assert status(rt)["manual_hold"]
        assert not status(rt)["monitoring_healthy"]
        assert rt.ingest(obs)["duplicate"]
        # Pruning id history must not reset the timestamp watermark.
        with rt.store.db:
            rt.store.db.execute("DELETE FROM observations")
        retry = obs.model_copy(update={"observation_id": "new-id"})
        with pytest.raises(ValueError, match="out-of-order"):
            rt.ingest(retry)
    finally:
        rt.close()


def test_database_has_single_owner(clock, tmp_path):
    cfg = demo_config(str(tmp_path / "state.sqlite3"))
    rt = Runtime(cfg, clock.monotonic, clock.wall)
    try:
        with pytest.raises(RuntimeError, match="owner"):
            Runtime(cfg, clock.monotonic, clock.wall)
    finally:
        rt.close()


def test_clock_jump_latches_unknown(runtime, clock):
    send(runtime, clock, 1)
    clock.epoch += 60
    assert runtime.status()["clock_fault"]
    assert not status(runtime)["monitoring_healthy"]


def test_bounded_journal(runtime, clock):
    for i in range(150):
        send(runtime, clock, i)
    runtime.store.prune(clock.wall(), 7, 100, 100)
    assert runtime.store.db.execute("SELECT count(*) FROM observations").fetchone()[0] == 100
    assert runtime.store.db.execute("SELECT count(*) FROM events").fetchone()[0] <= 100
