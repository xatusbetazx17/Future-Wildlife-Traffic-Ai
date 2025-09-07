from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict
from datetime import date

@dataclass
class VaccinationCampaign:
    """Agency-only planning record. No field procedures provided."""
    id: str
    name: str
    pathogen: str
    target_species: List[str]
    start_date: date
    end_date: date
    region_label: str
    approvals_received: bool = False
    target_population_estimate: Optional[int] = None
    target_coverage_rate: float = 0.0
    buffer_overage_rate: float = 0.10
    notes: str = ""

    def expected_dose_count(self) -> Optional[int]:
        if self.target_population_estimate is None or self.target_coverage_rate <= 0:
            return None
        base = int(round(self.target_population_estimate * self.target_coverage_rate))
        buffer = int(round(base * self.buffer_overage_rate))
        return max(0, base + buffer)

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["start_date"] = self.start_date.isoformat()
        d["end_date"] = self.end_date.isoformat()
        d["expected_dose_count"] = self.expected_dose_count()
        return d

def calc_expected_doses(population_estimate: int, coverage_rate: float, buffer_overage_rate: float = 0.10) -> int:
    base = int(round(max(0, population_estimate) * max(0.0, min(1.0, coverage_rate))))
    buffer = int(round(base * max(0.0, buffer_overage_rate)))
    return base + buffer