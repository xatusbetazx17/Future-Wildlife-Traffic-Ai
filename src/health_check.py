from dataclasses import dataclass
from typing import Optional, Dict
import random
import time

@dataclass
class HealthReport:
    temperature_c: float
    fever_flag: bool
    notes: str = ""

class HealthChecker:
    """Simulated non-invasive health checker.
    Replace with real sensors (IR thermography, etc.) in deployment."""
    def __init__(self, normal_temp_range=(36.0, 39.5)):
        self.normal_temp_range = normal_temp_range

    def check(self, species: Optional[str] = None) -> HealthReport:
        base_min, base_max = self.normal_temp_range
        # Adjust slightly by species (toy example)
        if species in {"deer","elk"}:
            base_max += 0.3

        temp = random.uniform(base_min - 0.7, base_max + 0.7)
        fever = temp > base_max
        notes = "Simulated reading; non-diagnostic."
        return HealthReport(temperature_c=round(temp,2), fever_flag=fever, notes=notes)