"""Deterministic synthetic observations; no hardware or real-world claims."""

from datetime import datetime, timezone

from .config import AppConfig
from .models import Observation
from .runtime import Runtime


class SimClock:
    def __init__(self):
        self.t = 0.0
        self.epoch = 1788998400.0

    def monotonic(self):
        return self.t

    def wall(self):
        return self.epoch + self.t

    def advance(self, seconds):
        self.t += seconds


def demo_config(database_path=":memory:"):
    return AppConfig.model_validate(
        {
            "mode": "simulation",
            "database_path": database_path,
            "sites": [
                {
                    "id": "demo",
                    "name": "Synthetic test corridor",
                    "latitude": 0,
                    "longitude": 0,
                    "confirm_frames": 2,
                    "confirm_window_s": 2,
                    "traffic": {
                        "min_green_s": 2,
                        "min_yellow_s": 1,
                        "min_red_s": 1,
                        "animal_crossing_hold_s": 2,
                        "clear_s": 1,
                        "max_crossing_s": 10,
                    },
                    "sensors": [{"id": "north", "max_age_s": 2, "allowed_conditions": ["dry"]}],
                }
            ],
        }
    )


def observation(
    clock,
    index,
    *,
    site="demo",
    sensor="north",
    label=None,
    conditions="dry",
    healthy=True,
    evidence="classified",
):
    return Observation(
        observation_id="obs-" + str(index),
        site_id=site,
        sensor_id=sensor,
        observed_at=datetime.fromtimestamp(clock.wall(), timezone.utc),
        healthy=healthy,
        conditions=conditions,
        detections=[{"label": label, "confidence": 0.95, "bbox": [0.2, 0.2, 0.7, 0.8], "evidence": evidence}]
        if label
        else [],
    )


def run_demo():
    clock = SimClock()
    rt = Runtime(demo_config(), clock.monotonic, clock.wall)
    timeline = []
    try:
        for i in range(60):
            clock.advance(0.5)
            label = "deer" if 10 <= i <= 20 else None
            # Deliberate outage followed by recovery.
            if not 30 <= i <= 39:
                rt.ingest(observation(clock, i, label=label))
            state = rt.status()["sites"][0]
            signature = (state["phase"], state["advisory"])
            if not timeline or signature != (timeline[-1]["phase"], timeline[-1]["advisory"]):
                timeline.append(
                    {"elapsed_s": clock.t, "phase": state["phase"], "advisory": state["advisory"]}
                )
        return {
            "evidence": "synthetic software simulation only",
            "physical_control": False,
            "observations": rt.observations_accepted,
            "timeline": timeline,
            "final_monitoring_healthy": rt.status()["sites"][0]["monitoring_healthy"],
        }
    finally:
        rt.close()
