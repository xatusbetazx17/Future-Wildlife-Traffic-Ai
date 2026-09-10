# Field validation and implementation plan

No field measurements, installed hardware, representative wildlife video, trained model or road-authority acceptance was available in this development session. Automated tests establish software behavior, not collision reduction, animal-detection accuracy, weather reliability or roadway suitability.

## Evidence gates

| Gate | Work and evidence required | Owner |
| --- | --- | --- |
| Site definition | Road geometry, sight distances, approach speeds, species, weather, detection coverage and local constraints | Transportation engineer and wildlife specialist |
| Data and model | Licensed data, independent labels, train/validation/test separation, held-out sites/seasons and model card | ML and ecology teams |
| Bench test | Target CPU/GPU, camera/thermal calibration, acquisition timestamp, latency, frame age, memory and power faults | Device integrator |
| Hardware in the loop | Controller feedback, interlocks, link failure, timing and recovery recorded on a closed bench | Controller vendor |
| Shadow field pilot | Live observations with no traffic actuation; independent ground-truth collection and failure review | Site authority and evaluation team |
| Limited authorized pilot | Approved design, operating envelope, monitoring owner, stop criteria and rollback | Responsible authority |
| Operational release | Completed evidence package, security review, maintenance schedule and sustained performance | Deploying company |

No software flag bypasses these steps or creates a certified control output.

## Equipment and integration inventory

Specify equipment against measured requirements, not an unverified universal bill of materials.

- Edge computer with supported OS, storage endurance, hardware watchdog, thermal capacity and measured inference headroom.
- Weather-rated RGB and/or thermal acquisition, appropriate lenses, mounts, cleaning and alignment provisions; independent coverage for occluded areas.
- Optional radar or other sensing with a tested semantic adapter; raw motion is insufficient to classify wildlife.
- Reliable power, surge/lightning protection and backup sized from measured peak power and the site's outage duration.
- Monitored network, time synchronization, authenticated gateway and local behavior during backhaul loss.
- Independently approved roadside signs/controllers and feedback interfaces if later authorized; these are not bundled hardware.
- Separate truth recording approved by the site owner. The service itself retains event metadata, not video.

Example engineering calculations: storage budget follows event rate × retention × measured bytes/event plus database overhead; battery energy must cover measured watts × outage hours divided by usable capacity/efficiency. Camera range and warning lead time must be validated against approach speed and sight distance, not inferred from a pixel box.

## Variables to include in the trial

| Dimension | Minimum scenarios to plan |
| --- | --- |
| Species and behavior | Local species, small/large animals, groups, stationary and moving animals, re-entry |
| Lighting and weather | Day/night, low sun, headlights, shadows, rain, fog, snow, lens contamination |
| Geometry | Distance, road curves, camera height, vegetation, partial occlusion, both road sides |
| Negative cases | People, pets, vehicles, insects, moving foliage, precipitation and thermal clutter |
| Timing | Slow inference, buffering, low frame rate, reordered/duplicate frames and clock correction |
| Failure | Disconnected/stuck sensor, reboot, disk full, power loss, blocked camera, broker and network outages |
| Operations | Hold/release, key rotation, model/config upgrade, rollback, alerts prolonged or missing |
| Human outcomes | Warning comprehension, distraction, false-warning burden and operator response |

A responsive camera does not prove its lens is clean or its view is useful. Test independent obstruction and scene-quality checks in the adapter; this repository does not yet implement them. Built-in OpenCV reads use acquisition-return timestamps, which cannot certify hidden backend buffering. Validate actual capture timestamps on the chosen device.

## Data and ML development

Collect representative licensed data with independent annotation and documented species/conditions. Split by encounter, time period and physical site so near-duplicate frames from one animal do not leak between training and evaluation. Include empty scenes and confusing negatives. Keep a holdout set untouched by threshold tuning.

Train the company-selected model in a separate controlled training environment. For Ultralytics, the official training entry point is `yolo detect train data=<dataset.yaml> model=<trusted-base-model.pt>`; choose epochs, image size and hardware using validation results. Pin the toolchain, record dataset/model hashes and preserve provenance. This repo intentionally does not download a model or pretend to have trained one.

Validate every requested label against the model. The standard COCO class list does not include deer or moose; selecting those strings does not create those capabilities. See the [official dataset class list](https://docs.ultralytics.com/datasets/detect/coco/).

Use [the model card](model_card.md) to record scope, licenses, limitations and per-slice results. Re-test after lens, firmware, model, ROI, species, weather envelope or timing changes.

## Measurement and acceptance

Before collecting test results, the site team must agree on measurable acceptance thresholds and stop rules. Do not copy arbitrary universal accuracy or latency targets from a demonstration.

Record detection opportunity, label, independent truth, warning issue/receipt time, confidence, site, species, weather, distance, visibility and hardware version. Measure misses as well as successful detections. Measure sensor uptime, false-warning duration, warnings/hour, end-to-end latency distribution, recovery duration and coverage. Assess animal detection separately from driver behavior and collision outcomes.

`python -m src.evaluation <labeled-windows.json> --output <report.json>` evaluates independent nonoverlapping windows, preserving synthetic/field provenance. It reports counts, precision, recall, false-positive rate, false-warning windows/hour, available latency samples and a Wilson recall interval. It cannot detect incorrect labels or a dishonest provenance tag. Frame classification metrics are not object-level mAP; correlated frames do not provide independent safety evidence.

The synthetic fixture deliberately contains a miss and a false warning. Its results are an arithmetic demonstration. Before claiming collision reduction, design an appropriately powered field study accounting for exposure and comparison sites with a qualified evaluator.

## Operating stop conditions

Suspend a field pilot's advisory integration on unexplained missed detections, unacceptable nuisance warnings, unsupported weather, failed timestamp integrity, broken sensor coverage, unexpected controller feedback, loss of auditability or breached credentials. The authority-approved hardware controller's fallback governs actual traffic. Preserve logs, investigate, revalidate and document restart authorization.

## Engineering references

- [FHWA MUTCD, current edition page](https://mutcd.fhwa.dot.gov/kno_11th_Editionr1.htm): roadway device/control design reference. This repository is not an implementation or certification of the manual.
- [FHWA Wildlife-Vehicle Collision Reduction Study, Chapter 5](https://www.fhwa.dot.gov/publications/research/safety/08034/05.cfm): historical review of animal detection and driver-warning measures, not proof of this product's performance.
- [Ultralytics COCO documentation](https://docs.ultralytics.com/datasets/detect/coco/): available classes and evaluation context.
- [Eclipse Paho Python client documentation](https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html): transport API behavior.

Check applicable local requirements, current versions and each provider's licenses for the actual deployment. No compliance certificate or agency approval is asserted.
