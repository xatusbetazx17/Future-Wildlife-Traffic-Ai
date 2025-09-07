# Vehicle & Navigation Integration (Draft)

This document summarizes how vehicles, ADAS, and navigation apps can consume wildlife corridor alerts.

## Feeds
- **Hotspots**: `GET /hotspots` — GeoJSON FeatureCollection (species, seasonality, notes).
- **Point Risk**: `GET /risk?lat=<>&lon=<>[&iso=YYYY-MM-DDTHH:MM]` — returns `risk: 0..100`, `advisory` string.
- **Events (optional)**: UDP/MQTT broadcast of `wildlife/events` (already in repo).

## JSON Example (Point Risk)
```json
{
  "lat": 40.987,
  "lon": -74.789,
  "iso": "2025-09-07T18:30:00-04:00",
  "risk": 72,
  "factors": ["dusk","fall","recent_detections"],
  "advisory": "Wildlife corridor at dusk (fall). Reduce speed and stay alert for deer."
}
```

## V2X (prototype mapping idea)
- **TIM-like advisory** (non-normative): include corridor polygon, validity window, advisory text, version/timestamp.
- **Security**: sign messages at the roadside unit; vehicles verify signature.
- **Fallback**: If V2X unavailable, nav apps can use the HTTP feed.

> This repo includes a simple UDP/MQTT publisher; OEMs can embed a listener in vehicles/dashcams to display an in-cabin warning.