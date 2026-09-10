"""Independent capture threads: blocked cameras cannot block the watchdog/API."""

import threading
import time
from pathlib import Path
from uuid import uuid4

from .detection import AnimalDetector
from .models import Observation, utc_string


class CaptureWorker:
    def __init__(self, runtime, site, sensor):
        self.runtime, self.site, self.sensor = runtime, site, sensor
        self.stop = threading.Event()
        self.last_error = None
        self.thread = threading.Thread(
            target=self.run, name="capture-" + site.id + "-" + sensor.id, daemon=True
        )

    def run(self):
        cap = None
        try:
            import cv2

            detector = AnimalDetector(
                self.sensor.model_path,
                self.site.confidence,
                self.site.species,
                self.sensor.model_sha256,
                self.sensor.detector,
            )
            if self.sensor.kind == "video":
                if not Path(self.sensor.source).is_file():
                    raise ValueError("video must be an existing local file")
            cap = cv2.VideoCapture()
            cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 3000)
            cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 3000)
            if not cap.open(self.sensor.source):
                raise RuntimeError("capture could not open")
            while not self.stop.is_set():
                started = time.monotonic()
                ok, frame = cap.read()
                observed = self.runtime.wall()  # Capture time, before potentially slow inference.
                if not ok:
                    self.last_error = "end_of_video" if self.sensor.kind == "video" else "capture_lost"
                    break  # EOF is terminal; never a busy infinite rewind loop.
                detections = detector.detect(frame)
                if self.stop.is_set():
                    break
                # Motion cannot establish wildlife coverage or produce healthy road clearance.
                healthy = self.sensor.detector != "motion"
                obs = Observation(
                    observation_id=str(uuid4()),
                    site_id=self.site.id,
                    sensor_id=self.sensor.id,
                    observed_at=utc_string(observed),
                    detections=detections if healthy else [],
                    conditions="unknown",
                    healthy=healthy,
                )
                self.runtime.ingest(obs)
                self.stop.wait(max(0, 1 / self.sensor.max_fps - (time.monotonic() - started)))
        except Exception as exc:
            self.last_error = type(exc).__name__
        finally:
            with self.runtime.lock:
                self.runtime.sensor_errors[(self.site.id, self.sensor.id)] = self.last_error
            if cap is not None:
                cap.release()
            if not self.stop.is_set():
                try:
                    self.runtime.ingest(
                        Observation(
                            observation_id=str(uuid4()),
                            site_id=self.site.id,
                            sensor_id=self.sensor.id,
                            observed_at=utc_string(self.runtime.wall()),
                            healthy=False,
                        )
                    )
                except Exception:
                    pass  # The independent watchdog still expires the last good observation.

    def close(self):
        self.stop.set()
        if self.thread.is_alive():
            self.thread.join(timeout=1)
