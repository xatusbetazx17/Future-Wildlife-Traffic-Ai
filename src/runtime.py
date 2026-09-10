"""One shared runtime for authenticated ingestion, monitoring and camera workers."""

import hashlib
import json
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from uuid import uuid4

from .config import AppConfig
from .geometry import inside
from .models import Event, Observation, utc_string
from .storage import Store
from .traffic_control import TrafficController


class RateLimitError(ValueError):
    pass


@dataclass
class SensorState:
    observed_mono: float | None = None
    healthy: bool = False
    conditions: str = "unknown"
    confirmations: dict = field(default_factory=lambda: defaultdict(deque))
    confirmed: dict = field(default_factory=dict)


class Runtime:
    def __init__(self, config: AppConfig, clock=time.monotonic, wall=time.time):
        self.config, self.clock, self.wall = config, clock, wall
        self.lock = threading.RLock()
        self.store = Store(config.database_path)
        self.sites = {s.id: s for s in config.sites}
        self.sensors = {(s.id, c.id): c for s in config.sites for c in s.sensors}
        self.states = {key: SensorState() for key in self.sensors}
        self.admission = defaultdict(deque)
        self.sensor_errors = {}
        self.controllers = {
            s.id: TrafficController(**s.traffic.model_dump(), clock=clock) for s in config.sites
        }
        self.holds = {s.id: self.store.held(s.id) for s in config.sites}
        self.last_signature, self.last_emit = {}, {}
        self.statuses = {}
        self.observations_accepted = 0
        self.observations_rejected = 0
        self.last_tick = clock()
        self.anchor_mono, self.anchor_wall = clock(), wall()
        self.clock_fault = False
        self.storage_fault = False
        self.worker_fault = False
        self.last_prune = clock()
        self.tick()

    def ingest(self, obs: Observation):
        with self.lock:
            try:
                key = (obs.site_id, obs.sensor_id)
                if key not in self.sensors:
                    raise ValueError("unknown site/sensor")
                sensor, site = self.sensors[key], self.sites[obs.site_id]
                now, epoch = self.clock(), self.wall()
                age = epoch - obs.observed_at.timestamp()
                if age < -1 or age > sensor.max_age_s:
                    raise ValueError("observation is stale or in the future")
                arrivals = self.admission[key]
                while arrivals and now - arrivals[0] >= 1:
                    arrivals.popleft()
                if len(arrivals) >= max(60, 2 * sensor.max_fps):
                    raise RateLimitError("sensor request rate exceeded; retry after one second")
                arrivals.append(now)
                digest = hashlib.sha256(
                    json.dumps(obs.model_dump(mode="json"), sort_keys=True).encode()
                ).hexdigest()
                if not self.store.accept(obs, digest, epoch):
                    return {"accepted": False, "duplicate": True}
                state = self.states[key]
                state.observed_mono = now - max(0, age)
                state.healthy = obs.healthy
                state.conditions = obs.conditions
                labels = set()
                if obs.healthy and obs.conditions in sensor.allowed_conditions:
                    for detection in obs.detections:
                        x1, y1, x2, y2 = detection.bbox
                        if (
                            detection.evidence == "classified"
                            and detection.label in site.species
                            and detection.confidence >= site.confidence
                            and inside(((x1 + x2) / 2, y2), sensor.roi)
                        ):
                            labels.add(detection.label)
                for label in set(state.confirmations) - labels:
                    state.confirmations[label].clear()
                for label in labels:
                    times = state.confirmations[label]
                    times.append(state.observed_mono)
                    while times and state.observed_mono - times[0] > site.confirm_window_s:
                        times.popleft()
                    while len(times) > site.confirm_frames:
                        times.popleft()
                    if len(times) >= site.confirm_frames:
                        state.confirmed[label] = state.observed_mono
                self.observations_accepted += 1
                self.tick()
                return {"accepted": True, "duplicate": False}
            except ValueError:
                self.observations_rejected += 1
                raise

    def tick(self):
        with self.lock:
            now, epoch = self.clock(), self.wall()
            if abs((epoch - self.anchor_wall) - (now - self.anchor_mono)) > 2:
                self.clock_fault = True  # Latch until restart after time synchronization.
            self.last_tick = now
            for site_id, site in self.sites.items():
                faults, optional_faults, labels, sensor_status = [], [], set(), {}
                for sensor in site.sensors:
                    state = self.states[(site_id, sensor.id)]
                    age = None if state.observed_mono is None else now - state.observed_mono
                    fresh = age is not None and 0 <= age <= sensor.max_age_s
                    usable = fresh and state.healthy and state.conditions in sensor.allowed_conditions
                    sensor_status[sensor.id] = {
                        "fresh": fresh,
                        "healthy": bool(usable),
                        "age_s": age,
                        "conditions": state.conditions,
                        "required": sensor.required,
                        "capture_error": self.sensor_errors.get((site_id, sensor.id)),
                    }
                    if not usable:
                        (faults if sensor.required else optional_faults).append(sensor.id)
                    for label, last in state.confirmed.items():
                        if now - last < site.traffic.clear_s:
                            labels.add(label)
                healthy = not (faults or self.clock_fault or self.storage_fault or self.worker_fault)
                state = self.controllers[site_id].update(
                    bool(labels), healthy=healthy, manual_hold=self.holds[site_id]
                )
                advisory = (
                    "operator_hold"
                    if self.holds[site_id]
                    else "wildlife_detected"
                    if labels
                    else "monitoring_unavailable"
                    if not healthy
                    else "no_recent_detection"
                )
                status = {
                    "site_id": site_id,
                    "name": site.name,
                    "mode": self.config.mode,
                    "physical_control": False,
                    "phase": state.phase.value,
                    "phase_is_simulated": True,
                    "animal_detected": bool(labels),
                    "species": sorted(labels),
                    "monitoring_healthy": healthy,
                    "required_sensor_faults": faults,
                    "optional_sensor_faults": optional_faults,
                    "sensors": sensor_status,
                    "manual_hold": self.holds[site_id],
                    "occupancy_overdue": state.occupancy_overdue,
                    "advisory": advisory,
                    "updated_at": utc_string(epoch),
                }
                signature = (
                    advisory,
                    tuple(sorted(labels)),
                    healthy,
                    state.phase.value,
                    self.holds[site_id],
                    state.occupancy_overdue,
                    tuple(faults),
                    tuple(optional_faults),
                )
                refresh = now - self.last_emit.get(site_id, -float("inf")) >= site.event_ttl_s / 2
                if signature != self.last_signature.get(site_id) or refresh:
                    event = {
                        "schema_version": 1,
                        "event_id": str(uuid4()),
                        "site_id": site_id,
                        "issued_at": utc_string(epoch),
                        "expires_at": utc_string(epoch + site.event_ttl_s),
                        "type": advisory,
                        "species": sorted(labels),
                        "monitoring_healthy": healthy,
                        "phase": state.phase.value,
                        "phase_is_simulated": True,
                        "mode": self.config.mode,
                        "physical_control": False,
                        "location": {
                            "latitude": site.latitude,
                            "longitude": site.longitude,
                            "radius_m": site.radius_m,
                        },
                        "advisory_speed_kph": site.advisory_speed_kph if labels else None,
                        "message": {
                            "wildlife_detected": "Wildlife detected near this corridor. Stay alert.",
                            "monitoring_unavailable": "Wildlife monitoring unavailable; road clearance is unknown.",
                            "operator_hold": "Operator has placed monitoring in hold.",
                            "no_recent_detection": "No recent confirmed detection; absence of wildlife is not guaranteed.",
                        }[advisory],
                    }
                    event = Event.model_validate(event).model_dump(mode="json")
                    self.store.event(event, epoch, site.event_ttl_s)
                    self.last_signature[site_id], self.last_emit[site_id] = signature, now
                self.statuses[site_id] = status
            if now - self.last_prune >= 30:
                self.store.prune(
                    epoch, self.config.retention_days, self.config.max_observations, self.config.max_events
                )
                self.last_prune = now

    def status(self):
        with self.lock:
            # Age data even when an embedding caller does not run a scheduler.
            self.tick()
            return json.loads(
                json.dumps(
                    {
                        "schema_version": 1,
                        "mode": self.config.mode,
                        "physical_control": False,
                        "clock_fault": self.clock_fault,
                        "storage_fault": self.storage_fault,
                        "worker_fault": self.worker_fault,
                        "sites": list(self.statuses.values()),
                        "observations_accepted": self.observations_accepted,
                        "observations_rejected": self.observations_rejected,
                        "mqtt_pending": self.store.pending_count(self.wall()),
                    }
                )
            )

    def set_hold(self, site_id, enabled, reason):
        with self.lock:
            if site_id not in self.sites:
                raise ValueError("unknown site")
            self.store.set_hold(site_id, enabled, reason, self.wall())
            self.holds[site_id] = enabled
            self.tick()

    def close(self):
        self.store.close()
