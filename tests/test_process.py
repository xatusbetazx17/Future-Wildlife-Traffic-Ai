"""A real HTTP socket/process test of the unified service and background watchdog."""

import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from src.simulation import demo_config


def test_service_watchdog_without_status_polling(tmp_path):
    cfg = demo_config(str(tmp_path / "service.sqlite3"))
    config = tmp_path / "config.json"
    config.write_text(cfg.model_dump_json())
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    read = "r" * 40
    sensor = "s" * 40
    env = dict(
        os.environ,
        WILDLIFE_API_KEY=read,
        WILDLIFE_ADMIN_KEY="",
        WILDLIFE_SENSOR_KEYS=json.dumps({"demo/north": sensor}),
    )
    process = subprocess.Popen(
        [sys.executable, "-m", "src.main", "--config", str(config), "serve", "--port", str(port)],
        env=env,
        cwd=Path(__file__).resolve().parents[1],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"

    def request(path, token=read, payload=None):
        data = None if payload is None else json.dumps(payload).encode()
        req = Request(
            base + path,
            data=data,
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        )
        with urlopen(req, timeout=2) as response:
            return json.load(response)

    try:
        deadline = time.monotonic() + 8
        while True:
            try:
                request("/healthz")
                break
            except (URLError, ConnectionError):
                assert process.poll() is None
                assert time.monotonic() < deadline
                time.sleep(0.05)
        request(
            "/v1/observations",
            sensor,
            {
                "observation_id": str(uuid4()),
                "site_id": "demo",
                "sensor_id": "north",
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "healthy": True,
                "conditions": "dry",
                "detections": [],
            },
        )
        assert request("/readyz")["ready"]
        cursor = request("/events")["next_cursor"]
        # /events does not tick the runtime. This requires the real background watchdog.
        deadline = time.monotonic() + 5
        while True:
            new = request("/events?after=" + str(cursor))["events"]
            if any(e["type"] == "monitoring_unavailable" for e in new):
                break
            assert time.monotonic() < deadline
            time.sleep(0.1)
        try:
            request("/readyz")
            raise AssertionError("expired sensor must not be ready")
        except HTTPError as exc:
            assert exc.code == 503
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
    assert process.returncode in (0, -15)
