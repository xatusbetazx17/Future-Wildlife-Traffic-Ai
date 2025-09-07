# Wildlife-Friendly Smart Traffic System (with Health Monitoring)

An open-source prototype that **detects wildlife near roads**, **adapts traffic signals in real-time** to prevent collisions, and **notifies vehicles** using V2X-style messaging. It also includes a **health-check abstraction** (simulated) to flag potential zoonotic risks for wildlife authorities.

> Vision: Combine **AI detection**, **smart traffic control**, and **connected comms** to reduce wildlife-vehicle collisions (up to ~80–90% in regions that install crossings and fencing, per multiple DOT studies) and to provide early signals for wildlife health events. This repo provides a **working software baseline** plus future-facing extension points.

---

## Features
- **AI animal detection** (YOLOv8 if available; motion-detection fallback).
- **Traffic signal controller** with an `ANIMAL_CROSSING` mode.
- **Emergency & weather-aware** timing adjustments.
- **V2X-style messaging** over MQTT + UDP broadcast (optional).
- **Streamlit dashboard** to monitor events and status.
- **Config via YAML**, clear logging, and testable logic (pytest).

> ⚠️ Privacy/Ethics: See `SECURITY.md`. The system is **road-safety oriented**; if capturing images, ensure legal compliance and disable storage where not required.

---

## Quickstart

### 1) Python
```bash
python -m venv .venv && source .venv/bin/activate  # (or .venv\Scripts\activate on Windows)
pip install -r requirements.txt
```

### 2) Run the core loop (camera 0 or a video path)
```bash
python -m src.main --camera 0 --config data/sample_config.yaml
# or
python -m src.main --video some_video.mp4
```

### 3) Dashboard (optional)
```bash
streamlit run dashboard/streamlit_app.py
```

### 4) API server (optional; read-only status)
```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

---

## Repository Layout
```
wildlife-traffic-system/
├── LICENSE
├── README.md
├── SECURITY.md
├── requirements.txt
├── .gitignore
├── data/
│   └── sample_config.yaml
├── docs/
│   └── vision_overview.md
├── dashboard/
│   └── streamlit_app.py
├── src/
│   ├── __init__.py
│   ├── utils.py
│   ├── config.py
│   ├── detection.py
│   ├── health_check.py
│   ├── traffic_control.py
│   ├── comms.py
│   └── main.py
├── tests/
│   └── test_scenarios.py
├── Dockerfile
└── docker-compose.yml
```

---

## Notes on AI models
- By default, the detector tries **Ultralytics YOLOv8** if installed (`ultralytics`).
- If the model cannot be loaded, the app falls back to **simple motion detection**.
- To use YOLO, place a model path in `sample_config.yaml` (`detection.model_path`) or leave it `null` to use default `yolov8n.pt` if available.

---

## Docker (optional)

```bash
docker build -t wildlife-traffic .
docker run --net=host --device /dev/video0 -e CAMERA_INDEX=0 wildlife-traffic
```

With MQTT broker:
```bash
docker compose up
```

---

## Roadmap (high-level)
- Multi-camera support & edge aggregation.
- Vehicle-class awareness (give way to emergency vehicles).
- Integrations with city ATMS systems (standards-based).
- Research plug-ins for **wildlife health** (non-invasive, compliant).
- Hardware-in-the-loop trials (Jetson/Raspberry Pi).