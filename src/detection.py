"""Explicit local inference. A failed wildlife model never becomes a motion classifier."""

import hashlib
from pathlib import Path

from .models import Detection


class AnimalDetector:
    def __init__(self, model_path, confidence, wildlife_labels, model_sha256=None, backend="yolo"):
        self.confidence, self.labels, self.backend = confidence, set(wildlife_labels), backend
        self.frames = 0
        import cv2

        self.cv2 = cv2
        if backend == "motion":
            self.model = cv2.createBackgroundSubtractorMOG2(history=200, varThreshold=32, detectShadows=True)
        elif backend == "yolo":
            if not model_path or not Path(model_path).is_file():
                raise ValueError(
                    "supply an existing, trusted local wildlife model; automatic downloads are disabled"
                )
            with open(model_path, "rb") as f:
                digest = hashlib.file_digest(f, "sha256").hexdigest()
            if not model_sha256 or digest != model_sha256:
                raise ValueError("model SHA-256 mismatch")
            from ultralytics import YOLO

            self.model = YOLO(model_path)
            names = self.model.names
            available = set(names.values() if isinstance(names, dict) else names)
            missing = self.labels - available
            if missing:
                raise ValueError("model lacks requested species classes: " + ", ".join(sorted(missing)))
        else:
            raise ValueError("unsupported detector")

    def detect(self, frame):
        if frame is None or frame.size == 0:
            raise ValueError("missing frame is a sensor fault, not an empty detection")
        h, w = frame.shape[:2]
        result = []
        if self.backend == "yolo":
            outputs = self.model.predict(source=frame, conf=self.confidence, verbose=False)
            for output in outputs:
                for box in output.boxes:
                    conf = float(box.conf.cpu().item())
                    label = output.names[int(box.cls.cpu().item())]
                    if label not in self.labels or conf < self.confidence:
                        continue
                    x1, y1, x2, y2 = box.xyxy.cpu().numpy().flatten()
                    bbox = [max(0, min(1, float(v))) for v in (x1 / w, y1 / h, x2 / w, y2 / h)]
                    if bbox[0] < bbox[2] and bbox[1] < bbox[3]:
                        result.append(Detection(label=label, confidence=conf, bbox=bbox))
        else:
            mask = self.model.apply(frame)
            self.frames += 1
            if self.frames < 20:
                return []  # Background warmup, still never evidence of wildlife.
            _, mask = self.cv2.threshold(mask, 254, 255, self.cv2.THRESH_BINARY)
            contours, _ = self.cv2.findContours(mask, self.cv2.RETR_EXTERNAL, self.cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours:
                if self.cv2.contourArea(contour) < 1500:
                    continue
                x, y, bw, bh = self.cv2.boundingRect(contour)
                result.append(
                    Detection(
                        label="unknown_motion",
                        confidence=0.0,
                        bbox=[x / w, y / h, (x + bw) / w, (y + bh) / h],
                        evidence="motion",
                    )
                )
        return result[:100]
