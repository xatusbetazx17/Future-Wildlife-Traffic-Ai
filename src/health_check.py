"""Optional research metadata. No disease inference or fabricated measurements."""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class HealthReport:
    surface_temperature_c: float | None
    source: str
    diagnostic: bool = False
    notes: str = "Surface temperature alone cannot diagnose fever, infection or zoonotic risk."


class HealthChecker:
    def check(self, *, surface_temperature_c=None, source="not_measured"):
        if surface_temperature_c is None:
            return HealthReport(None, "not_measured")
        if (
            isinstance(surface_temperature_c, bool)
            or not math.isfinite(surface_temperature_c)
            or not -100 <= surface_temperature_c <= 150
            or source == "not_measured"
        ):
            raise ValueError("a finite sensor measurement and explicit source are required")
        return HealthReport(float(surface_temperature_c), source)
