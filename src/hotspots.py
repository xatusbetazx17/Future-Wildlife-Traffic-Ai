"""Configuration-derived corridors and explicitly uncalibrated risk indices."""

from datetime import datetime
from zoneinfo import ZoneInfo

from .geometry import distance_m


def hotspots(runtime):
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": s.id,
                "geometry": {"type": "Point", "coordinates": [s.longitude, s.latitude]},
                "properties": {
                    "site_id": s.id,
                    "name": s.name,
                    "radius_m": s.radius_m,
                    "species": s.species,
                    "active_months": s.active_months,
                    "high_risk_hours": s.high_risk_hours,
                    "timezone": s.timezone,
                    "advisory_speed_kph": s.advisory_speed_kph,
                },
            }
            for s in runtime.config.sites
        ],
    }


def risk(runtime, lat, lon, at: datetime):
    if at.tzinfo is None:
        raise ValueError("time must include a UTC offset")
    statuses = {s["site_id"]: s for s in runtime.status()["sites"]}
    corridors = []
    live = abs(at.timestamp() - runtime.wall()) <= 60
    for site in runtime.config.sites:
        distance = distance_m(lat, lon, site.latitude, site.longitude)
        if distance > site.radius_m:
            continue
        local = at.astimezone(ZoneInfo(site.timezone))
        score, factors = site.base_risk, ["configured_base"]
        if local.month in site.active_months:
            score += 15
            factors.append("configured_season")
        if local.hour in site.high_risk_hours:
            score += 15
            factors.append("configured_time_window")
        status = statuses[site.id]
        if live and status["animal_detected"]:
            score += 40
            factors.append("recent_confirmed_detection")
        if live and not status["monitoring_healthy"]:
            factors.append("monitoring_unavailable")
        corridors.append(
            {
                "site_id": site.id,
                "distance_m": round(distance, 1),
                "risk": min(100, score),
                "factors": factors,
                "monitoring_healthy": status["monitoring_healthy"] if live else None,
            }
        )
    return {
        "schema_version": 1,
        "latitude": lat,
        "longitude": lon,
        "at": at.isoformat(),
        "risk": max((c["risk"] for c in corridors), default=None),
        "coverage": "configured_corridor" if corridors else "outside_configured_coverage",
        "calibrated": False,
        "is_collision_probability": False,
        "live_evidence_applied": live,
        "corridors": corridors,
        "advisory": "Stay alert for wildlife; this index does not establish road clearance.",
    }
