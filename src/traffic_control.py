from dataclasses import dataclass
from enum import Enum, auto
import time

class Phase(Enum):
    RED = auto()
    GREEN = auto()
    YELLOW = auto()
    ANIMAL_CROSSING = auto()

@dataclass
class TrafficState:
    phase: Phase = Phase.RED
    last_change_s: float = time.time()

class TrafficController:
    def __init__(self, min_green_s=8, min_yellow_s=3, min_red_s=6, animal_crossing_hold_s=15):
        self.min_green_s = min_green_s
        self.min_yellow_s = min_yellow_s
        self.min_red_s = min_red_s
        self.animal_crossing_hold_s = animal_crossing_hold_s
        self.state = TrafficState()

    def _elapsed(self) -> float:
        return time.time() - self.state.last_change_s

    def set_phase(self, phase: Phase):
        if self.state.phase != phase:
            self.state.phase = phase
            self.state.last_change_s = time.time()

    def update(self, animal_present: bool, vehicles_waiting: bool, emergency_vehicle: bool=False):
        now_phase = self.state.phase
        elapsed = self._elapsed()

        # Emergency takes priority
        if emergency_vehicle and not animal_present:
            if now_phase in (Phase.RED, Phase.ANIMAL_CROSSING, Phase.YELLOW) and elapsed >= self.min_red_s:
                self.set_phase(Phase.GREEN)
            return self.state

        if animal_present:
            # Enter/hold ANIMAL_CROSSING
            if now_phase != Phase.ANIMAL_CROSSING or elapsed >= self.animal_crossing_hold_s:
                self.set_phase(Phase.ANIMAL_CROSSING)
            return self.state

        # Normal cycle
        if now_phase == Phase.RED:
            if vehicles_waiting and elapsed >= self.min_red_s:
                self.set_phase(Phase.GREEN)
        elif now_phase == Phase.GREEN:
            if elapsed >= self.min_green_s:
                self.set_phase(Phase.YELLOW)
        elif now_phase == Phase.YELLOW:
            if elapsed >= self.min_yellow_s:
                self.set_phase(Phase.RED)
        elif now_phase == Phase.ANIMAL_CROSSING:
            # Clear back to RED after hold
            if elapsed >= self.animal_crossing_hold_s:
                self.set_phase(Phase.RED)

        return self.state