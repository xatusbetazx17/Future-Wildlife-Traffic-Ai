"""Evaluate labeled, nonoverlapping observation windows; never invent accuracy."""

import argparse
import json
import math
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, StrictBool, model_validator

from .config import FiniteFloat, Model


class Window(Model):
    id: str
    species: str
    condition: str
    animal_present: StrictBool
    warned: StrictBool
    duration_s: Annotated[FiniteFloat, Field(gt=0)]
    warning_latency_ms: Annotated[FiniteFloat, Field(ge=0)] | None = None

    @model_validator(mode="after")
    def valid_latency(self):
        if self.warning_latency_ms is not None and not (self.animal_present and self.warned):
            raise ValueError("latency is only defined for a true positive")
        return self


class Dataset(Model):
    schema_version: Literal[1] = 1
    provenance: Literal["synthetic", "field"]
    description: str
    windows: list[Window] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_windows(self):
        if len({w.id for w in self.windows}) != len(self.windows):
            raise ValueError("evaluation window IDs must be unique")
        return self


def ratio(a, b):
    return a / b if b else None


def wilson(success, total):
    if not total:
        return None
    z = 1.959963984540054
    p = success / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [max(0, center - margin), min(1, center + margin)]


def metrics(windows):
    tp = sum(w.animal_present and w.warned for w in windows)
    fn = sum(w.animal_present and not w.warned for w in windows)
    fp = sum(not w.animal_present and w.warned for w in windows)
    tn = sum(not w.animal_present and not w.warned for w in windows)
    latency = sorted(w.warning_latency_ms for w in windows if w.warning_latency_ms is not None)
    duration = sum(w.duration_s for w in windows)
    return {
        "windows": len(windows),
        "true_positive": tp,
        "false_negative": fn,
        "false_positive": fp,
        "true_negative": tn,
        "precision": ratio(tp, tp + fp),
        "recall": ratio(tp, tp + fn),
        "recall_wilson_95": wilson(tp, tp + fn),
        "false_positive_rate": ratio(fp, fp + tn),
        "false_warning_windows_per_hour": fp / (duration / 3600),
        "latency_samples": len(latency),
        "latency_p95_ms": latency[math.ceil(0.95 * len(latency)) - 1] if latency else None,
    }


def evaluate(data: Dataset):
    return {
        "schema_version": 1,
        "provenance": data.provenance,
        "description": data.description,
        "metrics": metrics(data.windows),
        "by_species": {
            s: metrics([w for w in data.windows if w.species == s])
            for s in sorted({w.species for w in data.windows})
        },
        "by_condition": {
            s: metrics([w for w in data.windows if w.condition == s])
            for s in sorted({w.condition for w in data.windows})
        },
        "limitations": "Nonoverlapping labeled windows are required. This is not an object-detection mAP evaluation or evidence of collision reduction. Correlated samples weaken the interval interpretation.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("--output")
    args = parser.parse_args()
    result = evaluate(Dataset.model_validate_json(Path(args.input).read_text()))
    text = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if args.output:
        Path(args.output).write_text(text)
    print(text)


if __name__ == "__main__":
    main()
