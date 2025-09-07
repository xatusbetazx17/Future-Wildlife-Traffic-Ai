# ROADMAP — Wildlife-Friendly Smart Traffic System

This roadmap organizes work into deliverable phases so transportation + wildlife agencies, vehicle OEMs, and map/GPS providers can adopt the system safely.

---

## Phase 0 — Foundations (2–4 weeks)
- **Hotspot data model (GeoJSON)**: species, seasonality (breeding/migration windows), time-of-day risk, and advisory speeds.
- **Risk API**: `/risk?lat&lon&time` returns 0–100 risk and advisory text.
- **Hotspots API**: `/hotspots` serves agency-curated GeoJSON (no PII).
- **Dashboard panel**: Hotspot list + current risk by time of day.

**Deliverables:** `data/hotspots.sample.geojson`, `src/hotspots.py`, new API routes, unit tests.

---

## Phase 1 — Public Alerts & Navigation (3–6 weeks)
- **GPS/Maps feed**: JSON feed (v0) that nav apps can poll or subscribe to.
- **Seasonal advisories**: dusk/dawn + breeding season notifications.
- **Driver UI text** (short, non-distracting): “Wildlife corridor ahead; reduce speed.”
- **Privacy-by-design**: no raw images, only anonymized alerts.

**Deliverables:** `src/gps_feed.py`, feed spec in `docs/vehicle_integration.md`.

---

## Phase 2 — Vehicle Integration & V2X (6–12 weeks)
- **V2X adapters** (prototype): map alerts to TIM-like messages; document mapping toward SAE J2735 family (non-normative).
- **On-vehicle client stub**: UDP/MQTT listener example for cars/dashcams/ADAS ECUs.
- **Advisory speed + lane-level hints** (advisory only).

**Deliverables:** sample V2X payloads, listener script, integration notes in `docs/vehicle_integration.md`.

---

## Phase 3 — Predictive Ecology & Scheduling (quarterly)
- **Seasonal models**: combine historical collisions, migration calendars, weather, sunrise/sunset.
- **Proactive signage schedules**: when/where to pre‑arm `ANIMAL_CROSSING` mode.
- **Agency-only vaccination planning**: continue at metadata level (no field protocols).

**Deliverables:** risk tuning docs, data connectors, evaluation reports.

---

## Phase 4 — Multi-Site Operations & Safety Case (ongoing)
- **Multi-corridor orchestration**; OTA configs; audit logs.
- **Functional safety**: documented fail-safes, timers/hysteresis, test matrix.
- **Security posture**: mTLS, SBOM, signed images, role-based access.

---

## Data Governance & Ethics (continuous)
- Keep images ephemeral; publish **event-only** data.
- Mask/blur sensitive content; respect agency policies and legal requirements.
- Vaccination remains **planning metadata only** (counts/dates). Field operations are out of scope here.