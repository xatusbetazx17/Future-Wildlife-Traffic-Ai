from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict
import yaml

@dataclass
class DetectionConfig:
    model_path: Optional[str] = None
    confidence: float = 0.35
    use_yolo: bool = True
    wildlife_labels: List[str] = field(default_factory=lambda: ["deer", "bear", "moose"])
    video_source: Any = 0

@dataclass
class TrafficConfig:
    min_green_s: int = 8
    min_yellow_s: int = 3
    min_red_s: int = 6
    animal_crossing_hold_s: int = 15
    emergency_priority: bool = True

@dataclass
class CommsConfig:
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_topic_events: str = "wildlife/events"
    udp_broadcast_port: int = 37020

@dataclass
class BehaviorConfig:
    enable_udp_broadcast: bool = True
    enable_mqtt: bool = False
    draw_debug: bool = True

@dataclass
class AppConfig:
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    traffic: TrafficConfig = field(default_factory=TrafficConfig)
    comms: CommsConfig = field(default_factory=CommsConfig)
    behavior: BehaviorConfig = field(default_factory=BehaviorConfig)

def load_config(path: str) -> AppConfig:
    with open(path, "r") as f:
        raw = yaml.safe_load(f) or {}
    def merge(dc, data: Dict):
        for k, v in data.items():
            if hasattr(dc, k):
                if isinstance(v, dict):
                    merge(getattr(dc, k), v)
                else:
                    setattr(dc, k, v)
    cfg = AppConfig()
    merge(cfg, raw)
    return cfg