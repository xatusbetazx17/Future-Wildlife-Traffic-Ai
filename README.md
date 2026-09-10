# Future Wildlife Traffic AI

A runnable, configurable **shadow-pilot toolkit** for wildlife observations, corridor advisories, and traffic-signal simulation. Companies can adapt the sensor API and event feed to their own equipment and evaluate the result before field deployment.

**Version 0.2 is a software pilot, not a certified roadway controller or a field-validated animal detector.** It never operates physical signals, brakes, barriers, or vaccination equipment. No trained regional wildlife model, collision-reduction evidence, or disease diagnostic is bundled.

## What runs now

- Multiple independent sites and sensors; species, confidence, image zones, confirmation windows, weather envelope, freshness, and timing are configurable.
- Authenticated sensor ingestion with per-sensor credentials, timestamp/replay checks, bounded requests and duplicate handling.
- A single shared runtime for camera workers, the API, and the integrated browser dashboard.
- A signal simulator with minimum green, yellow and red clearance, occupancy hold, fault handling, and persistent operator holds.
- SQLite event journal and expiring HTTP/MQTT 5 advisories; optional TLS/mTLS MQTT, QoS 1 and an outbox.
- Hotspot GeoJSON, timezone-aware seasonal risk indices, health/readiness checks, and Prometheus-style metrics.
- Local model SHA-256 checks and species-label verification. Missing models fail explicitly. Motion is never identified as wildlife.
- Deterministic simulation, automated fault tests, labeled-window evaluation, JSON Schemas, OpenAPI and deployment examples.
- Health metadata contains only supplied measurements; the old random temperature/fever generator has been removed.

See [company integration](docs/company_integration.md), [field validation](docs/field_validation.md), and [validation evidence](docs/validation.md).

## Run the software demonstration

Python 3.11+; the locally verified environment is recorded in the validation report.

```bash
git clone https://github.com/xatusbetazx17/Future-Wildlife-Traffic-Ai.git
cd Future-Wildlife-Traffic-Ai
git switch codex/implementation-ready-pilot
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[test,mqtt]"
python -m src.main --config configs/pilot.yaml validate
python -m src.main demo
```

On Windows, activate with `.venv\Scripts\Activate.ps1` in PowerShell. Run the equivalent environment-variable commands there. Configurations with IANA timezone names need system timezone data or the included `tzdata` dependency.

The demo supplies synthetic observations, a wildlife crossing, a sensor outage, and recovery. It requires neither a camera nor a model and does not establish detection accuracy.

## Dashboard and live API

In a shell where the virtual environment is active:

```bash
export WILDLIFE_API_KEY="$(python -m src.main token)"
export WILDLIFE_ADMIN_KEY="$(python -m src.main token)"
export WILDLIFE_SENSOR_TOKEN="$(python -m src.main token)"
export WILDLIFE_SENSOR_KEYS="$(python -c 'import json,os; print(json.dumps({"corridor-demo/north":os.environ["WILDLIFE_SENSOR_TOKEN"]}))')"
python -m src.main --config configs/pilot.yaml serve
```

Open **http://127.0.0.1:8000** and enter the read token from `WILDLIFE_API_KEY`. The token stays in page memory. API documentation is at `/docs`. Save credentials in your own secret manager; do not commit them.

From another shell with the same sensor token, send a bounded synthetic stream:

```bash
python examples/send_observations.py --seconds 30
```

No sensor data is fabricated by the server. A fresh installation reports monitoring unavailable until all required sensors send valid, current observations. When this demonstration stops, monitoring becomes unavailable again.

Use one service process per database. Do not start a separate detection process plus an unrelated API process, use multiple Uvicorn workers, or share this SQLite database across hosts.

## Real camera or vendor sensor

For camera inference, install `python -m pip install -e ".[vision]"`, provide a trusted, locally trained model, update its SHA-256 and class names in [camera.yaml](configs/camera.yaml), then run the same service with that configuration. The example's placeholder hash/model will deliberately fail.

General COCO models do not cover every regional wildlife species. The adapter checks **all** requested labels and rejects an incompatible model. No fallback silently converts a failed model to animal detections. OpenCV motion processing is available only as a non-classifying diagnostic.

RGB/thermal camera vendors, radar classifiers, or sensor-fusion systems can instead send validated observations to `POST /v1/observations`. They must map their classifications and coverage into the documented contract; no universal radar or thermography driver is claimed. Built-in video sources stop at EOF. Capture faults require operator inspection and a service restart; external sensor streams recover through fresh observations.

## Adaptation

Start with [pilot.yaml](configs/pilot.yaml) or [multisite.yaml](configs/multisite.yaml). Sample locations and seasonal settings are illustrative.

| Configuration | Purpose |
| --- | --- |
| Site ID, coordinates, radius, timezone | Independent corridor and risk time windows |
| Species, confidence, confirmation frames/window | Class filtering and temporal confirmation |
| Sensor ROI, required flag, maximum age | Coverage, freshness and fault behavior |
| Allowed conditions | Mark unsupported weather or unknown conditions unavailable |
| Green/yellow/red, hold/clear intervals | Simulator timing, subject to future site engineering |
| Event TTL, retention and row limits | Freshness, bounded storage and delivery |
| MQTT certificate and credential paths | Optional authenticated transport |

Unknown configuration keys are rejected. Paths resolve relative to the configuration file. Changing configuration requires a controlled restart. There is no `live` mode or physical-output switch.

## Test and evaluate

```bash
python -m pip install -e ".[test,mqtt]" opencv-python-headless
python -m pytest -q
python -m ruff check src tests examples
python -m src.evaluation examples/evaluation.synthetic.json
python -m build
```

The evaluation command also accepts properly labeled field windows and reports precision, recall, false-positive rate, false-warning windows per hour, latency samples and recall intervals. Synthetic results are explicitly labeled; missing denominators remain unknown.

## Deployment

`docker compose up --build` uses the credentials above, loopback networking, an unprivileged container and a persistent data volume. The default image runs external sensor ingestion; camera/AI dependencies are optional and need an integrator-specific image. See [deployment](docs/deployment.md) for systemd, TLS, backup, rollback, resource limits and platform verification.

## Commercial adoption and remaining work

The repository's original [MIT license](LICENSE) is preserved. Dependency, dataset, model-weight and protocol licenses are separate; review them for your product. Ultralytics is an optional dependency with its own terms.

Companies still need representative labeled footage, validated model weights, sensor calibration, edge hardware testing, field trials, a road-authority-approved integration and an operational safety case. Standardized automotive V2X and public-road controller adapters are not implemented here. See [the explicit roadmap](ROADMAP.md). This software makes no collision-reduction or disease-detection claim.
