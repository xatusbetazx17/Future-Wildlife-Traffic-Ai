"""External sensor contract demonstration. Uses only the standard library."""

import argparse
import json
import os
import time
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--site", default="corridor-demo")
    parser.add_argument("--sensor", default="north")
    parser.add_argument("--seconds", type=int, default=30)
    parser.add_argument("--species", default="deer")
    args = parser.parse_args()
    token = os.environ["WILDLIFE_SENSOR_TOKEN"]
    for index in range(args.seconds * 5):
        animal = 20 <= index < 60
        obs = {
            "schema_version": 1,
            "observation_id": str(uuid4()),
            "site_id": args.site,
            "sensor_id": args.sensor,
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "healthy": True,
            "conditions": "dry",
            "detections": [
                {
                    "label": args.species,
                    "confidence": 0.95,
                    "bbox": [0.2, 0.3, 0.7, 0.8],
                    "evidence": "classified",
                }
            ]
            if animal
            else [],
        }
        request = Request(
            args.url.rstrip("/") + "/v1/observations",
            data=json.dumps(obs).encode(),
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=5) as response:
            if index % 5 == 0:
                print("synthetic observation", index, response.status)
        time.sleep(0.2)


if __name__ == "__main__":
    main()
