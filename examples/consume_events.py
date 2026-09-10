"""Read only, bounded HTTP consumer; no vehicle or signal commands."""

import argparse
import json
import os
import time
from datetime import datetime, timezone
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--seconds", type=int, default=30)
    args = parser.parse_args()
    token = os.environ["WILDLIFE_API_KEY"]
    cursor = 0
    latest = {}
    for _ in range(args.seconds):
        request = Request(
            args.url.rstrip("/") + f"/events?after={cursor}", headers={"Authorization": "Bearer " + token}
        )
        with urlopen(request, timeout=5) as response:
            feed = json.load(response)
        now = datetime.now(timezone.utc)
        for event in feed["events"]:
            if event["schema_version"] != 1 or event["physical_control"] is not False:
                raise ValueError("unsupported advisory format")
            if datetime.fromisoformat(event["expires_at"]) <= now:
                continue
            latest[event["site_id"]] = event
        cursor = feed["next_cursor"]
        latest = {
            site: event for site, event in latest.items() if datetime.fromisoformat(event["expires_at"]) > now
        }
        print(json.dumps({site: event["message"] for site, event in latest.items()}))
        time.sleep(1)


if __name__ == "__main__":
    main()
