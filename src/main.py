import argparse
import time
import cv2
from typing import Optional
from fastapi import FastAPI
from pydantic import BaseModel

from .config import load_config
from .detection import AnimalDetector, Detection
from .health_check import HealthChecker
from .traffic_control import TrafficController, Phase
from .comms import Broadcaster
from .utils import get_logger, banner

app = FastAPI(title="Wildlife Traffic System", version="0.1.0")
logger = get_logger()

class Status(BaseModel):
    phase: str
    last_event: Optional[str] = None
    animal_detected: bool = False

STATE = {"phase": "INIT", "last_event": None, "animal_detected": False}

@app.get("/status", response_model=Status)
def status():
    return Status(**STATE)

def run_loop(cfg_path: str, video: Optional[str]=None, camera: Optional[int]=None):
    cfg = load_config(cfg_path)
    banner("Wildlife-Friendly Smart Traffic System")
    logger.info("Starting with config: %s", cfg_path)

    # Detector & Health
    detector = AnimalDetector(
        model_path=cfg.detection.model_path,
        confidence=cfg.detection.confidence,
        wildlife_labels=cfg.detection.wildlife_labels,
        use_yolo=cfg.detection.use_yolo
    )
    health = HealthChecker()

    # Comms
    comms = Broadcaster(
        mqtt_host=cfg.comms.mqtt_host,
        mqtt_port=cfg.comms.mqtt_port,
        topic=cfg.comms.mqtt_topic_events,
        udp_port=cfg.comms.udp_broadcast_port,
        enable_mqtt=cfg.behavior.enable_mqtt,
        enable_udp=cfg.behavior.enable_udp_broadcast
    )

    # Traffic
    tc = TrafficController(
        min_green_s=cfg.traffic.min_green_s,
        min_yellow_s=cfg.traffic.min_yellow_s,
        min_red_s=cfg.traffic.min_red_s,
        animal_crossing_hold_s=cfg.traffic.animal_crossing_hold_s
    )

    # Video source
    cap = None
    if video is not None:
        cap = cv2.VideoCapture(video)
    else:
        src = camera if camera is not None else cfg.detection.video_source
        cap = cv2.VideoCapture(src)

    if not cap.isOpened():
        logger.warning("Video source could not be opened. Running headless (no frames).")

    last_event_txt = None

    try:
        while True:
            ret, frame = (False, None)
            if cap and cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # loop videos
                    continue

            # Detect
            detections = detector.detect(frame) if ret else []
            animal_present = len(detections) > 0

            # Simple example: health check on first detection's label
            if animal_present:
                report = health.check(detections[0].label if detections else None)
                event = {
                    "type": "animal_detected",
                    "species": detections[0].label if detections else "wildlife",
                    "fever_flag": report.fever_flag,
                    "temperature_c": report.temperature_c,
                    "ts": time.time(),
                }
                comms.publish(event)
                last_event_txt = f"{event['species']} detected (fever={event['fever_flag']}, T={event['temperature_c']})"
                logger.info(last_event_txt)

            # Update traffic
            # For simplicity, vehicles_waiting=True when no animal is present
            st = tc.update(
                animal_present=animal_present,
                vehicles_waiting=(not animal_present),
                emergency_vehicle=False
            )

            STATE["phase"] = st.phase.name
            STATE["animal_detected"] = animal_present
            STATE["last_event"] = last_event_txt

            # Debug view
            if ret and cfg.behavior.draw_debug:
                if animal_present:
                    frame = AnimalDetector.draw(frame, detections)
                cv2.putText(frame, f"PHASE: {st.phase.name}", (10,30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0,200,255), 2)
                cv2.imshow("Wildlife Traffic", frame)
                if cv2.waitKey(1) & 0xFF == 27:  # ESC to quit
                    break

            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        if cap:
            cap.release()
        cv2.destroyAllWindows()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, default="data/sample_config.yaml")
    parser.add_argument("--video", type=str, default=None, help="Video file path")
    parser.add_argument("--camera", type=int, default=None, help="Camera index (e.g., 0)")
    args = parser.parse_args()
    run_loop(args.config, video=args.video, camera=args.camera)

if __name__ == "__main__":
    main()