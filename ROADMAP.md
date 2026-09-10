# Implementation status and remaining work

## Implemented in version 0.2

- Strict, versioned per-site and per-sensor configuration.
- Independent site state, normalized ROIs, species/confidence filtering and repeated-observation confirmation.
- Scoped sensor ingestion with timestamp, duplicate/replay, size and request-rate checks.
- Freshness and weather-envelope faults, persistent manual hold, conservative traffic simulation.
- Shared API/capture/dashboard service with an independent watchdog.
- SQLite journal, watermarks, TTL advisories, HTTP cursors and optional TLS MQTT outbox.
- Configured hotspot GeoJSON and explicitly uncalibrated local-time seasonal risk.
- Trusted local YOLO adapter with hash/class checks; motion cannot establish wildlife presence.
- No fabricated wildlife temperature or fever data.
- Unit, API, failure, generated-video and actual-process tests; deterministic demo; evaluation tool.
- Integration contracts, configuration/observation/event schemas, company/field guides, packaging and deployment examples.

## Required before a measured site pilot

- Collect and label representative licensed data; train and evaluate site/species models.
- Acquire and calibrate devices, validate detection range, occlusion and frame age.
- Validate native camera reconnection and vendor-specific radar/thermal interfaces.
- Measure hardware load, latency, storage, reliability and behavior under power/network failures.
- Establish baseline false-warning/miss rates and operating envelope with independent ground truth.

## Required before public-road control or automotive deployment

- Responsible-authority engineering approval and complete safety case.
- Vendor-specific controller integration with real feedback, hardware interlocks and all traffic movements.
- Approved roadside-device behavior, human-factors evaluation and operation/maintenance ownership.
- Any required licensed/standardized V2X encoding, radio security and vehicle integration.
- Representative field evidence; outcome studies before collision-reduction claims.

## Future company-scale development

- Authenticated fleet provisioning, signed artifacts/configs, staged OTA and device inventory.
- Distributed aggregation/availability design and audited enterprise identity integration.
- Geographic corridor imports beyond configured circular sites.
- Calibrated ecological prediction and astronomical time windows if supported by data.
- Hardware quality/obstruction detection and regional model drift evaluation.
- Long-term monitored deployments and independent security review.

These are explicit outstanding engineering tasks, not capabilities activated by configuration. No universal company compatibility, field certification or complete real-world validation is claimed.
