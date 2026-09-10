"""Single-movement signal SIMULATOR; never drives public-road signals."""

import math
import time
from dataclasses import dataclass
from enum import Enum


class Phase(str, Enum):
    RED = "RED"
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    ANIMAL_CROSSING = "ANIMAL_CROSSING"
    FAULT = "FAULT"


@dataclass
class TrafficState:
    phase: Phase
    last_change_s: float
    occupancy_overdue: bool = False


class TrafficController:
    def __init__(
        self,
        min_green_s=8,
        min_yellow_s=3,
        min_red_s=6,
        animal_crossing_hold_s=15,
        clear_s=5,
        max_crossing_s=120,
        clock=time.monotonic,
    ):
        values = (min_green_s, min_yellow_s, min_red_s, animal_crossing_hold_s, clear_s, max_crossing_s)
        if any(isinstance(v, bool) or not math.isfinite(v) or v <= 0 for v in values):
            raise ValueError("all simulator durations must be finite and positive")
        self.min_green_s, self.min_yellow_s, self.min_red_s = values[:3]
        self.animal_crossing_hold_s, self.clear_s, self.max_crossing_s = values[3:]
        self.clock = clock
        now = clock()
        self.state = TrafficState(Phase.RED, now)
        self.last_seen = None
        self.clear_since = None
        self.last_tick = now

    def update(
        self,
        animal_present: bool,
        vehicles_waiting: bool = True,
        emergency_vehicle: bool = False,
        healthy: bool = True,
        manual_hold: bool = False,
    ):
        now = self.clock()
        if now < self.last_tick or not math.isfinite(now):
            raise ValueError("controller requires a finite monotonic clock")
        self.last_tick = now
        if animal_present:
            self.last_seen = now
        hazard = animal_present or not healthy or manual_hold
        if hazard:
            self.clear_since = None
        elif self.clear_since is None:
            self.clear_since = now
        clear = self.clear_since is not None and now - self.clear_since >= self.clear_s
        recent = self.last_seen is not None and now - self.last_seen < self.clear_s
        phase, elapsed = self.state.phase, now - self.state.last_change_s
        target = phase
        if phase == Phase.GREEN:
            if (hazard or recent) and elapsed >= self.min_green_s:
                target = Phase.YELLOW
        elif phase == Phase.YELLOW:
            if elapsed >= self.min_yellow_s:
                target = Phase.RED
        elif phase == Phase.RED:
            if elapsed >= self.min_red_s:
                if not healthy or manual_hold:
                    target = Phase.FAULT
                elif animal_present or recent:
                    target = Phase.ANIMAL_CROSSING
                elif clear and (vehicles_waiting or emergency_vehicle):
                    target = Phase.GREEN
        elif phase == Phase.ANIMAL_CROSSING:
            self.state.occupancy_overdue = elapsed >= self.max_crossing_s
            if not healthy or manual_hold:
                target = Phase.FAULT
            elif clear and elapsed >= self.animal_crossing_hold_s:
                target = Phase.RED
        elif phase == Phase.FAULT:
            if healthy and not manual_hold:
                target = Phase.RED
        if target != phase:
            self.state = TrafficState(target, now)
        return self.state
