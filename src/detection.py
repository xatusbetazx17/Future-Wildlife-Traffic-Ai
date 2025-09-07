from dataclasses import dataclass
from typing import List, Optional
import numpy as np

try:
    from ultralytics import YOLO
    _HAS_YOLO = True
except Exception:
    _HAS_YOLO = False

import cv2

@dataclass
class Detection:
    label: str
    confidence: float
    bbox: tuple  # (x1, y1, x2, y2)

class AnimalDetector:
    def __init__(self, model_path: Optional[str], confidence: float, wildlife_labels: List[str], use_yolo: bool = True):
        self.confidence = float(confidence)
        self.wildlife_labels = set([w.lower() for w in wildlife_labels])
        self.use_yolo = use_yolo and _HAS_YOLO
        self.model = None
        if self.use_yolo:
            try:
                self.model = YOLO(model_path or "yolov8n.pt")
            except Exception:
                self.model = None
                self.use_yolo = False

        # Motion fallback
        self.fgbg = cv2.createBackgroundSubtractorMOG2(history=200, varThreshold=32, detectShadows=True)

    def detect(self, frame: np.ndarray) -> List[Detection]:
        if frame is None or frame.size == 0:
            return []

        if self.use_yolo and self.model is not None:
            results = self.model.predict(source=frame, verbose=False)
            dets: List[Detection] = []
            for r in results:
                for b in r.boxes:
                    conf = float(b.conf.cpu().item())
                    if conf < self.confidence:
                        continue
                    cls_id = int(b.cls.cpu().item())
                    label = r.names.get(cls_id, "object").lower()
                    if self.wildlife_labels and label not in self.wildlife_labels:
                        continue
                    x1, y1, x2, y2 = map(lambda x: int(x), b.xyxy.cpu().numpy().flatten())
                    dets.append(Detection(label=label, confidence=conf, bbox=(x1, y1, x2, y2)))
            return dets

        # Fallback: motion detection -> coarse bounding boxes
        fgmask = self.fgbg.apply(frame)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3,3))
        fgmask = cv2.morphologyEx(fgmask, cv2.MORPH_OPEN, kernel, iterations=2)
        contours, _ = cv2.findContours(fgmask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        dets = []
        h, w = frame.shape[:2]
        for c in contours:
            if cv2.contourArea(c) < 1500:  # filter small blobs
                continue
            x, y, bw, bh = cv2.boundingRect(c)
            x1, y1, x2, y2 = x, y, x + bw, y + bh
            # label unknown in fallback
            dets.append(Detection(label="wildlife", confidence=0.5, bbox=(x1, y1, x2, y2)))
        return dets

    @staticmethod
    def draw(frame: np.ndarray, detections: List[Detection]):
        for d in detections:
            x1, y1, x2, y2 = d.bbox
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, f"{d.label} {d.confidence:.2f}", (x1, max(0, y1-5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 1)
        return frame