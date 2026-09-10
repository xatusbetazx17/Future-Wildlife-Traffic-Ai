# Model card template — not yet populated with a validated model

| Required record | Integrator entry |
| --- | --- |
| Model owner, name, version and SHA-256 | Not supplied |
| Model code and weight licenses | Not supplied |
| Training data provenance and license | Not supplied |
| Label taxonomy and requested site species | Not supplied |
| Training/validation/test split strategy | Not supplied |
| Training command, seed and environment | Not supplied |
| Independent held-out sites and seasons | Not supplied |
| Per-species precision/recall and object-level metrics | Not measured |
| Day/night/weather/distance performance | Not measured |
| False warnings per monitoring hour | Not measured |
| Full detection-to-consumer latency distribution | Not measured |
| Hardware/OS/camera/firmware and power budget | Not measured |
| Occlusion/contamination/unknown-condition behavior | Not measured |
| Known failure modes and excluded conditions | Not measured |
| Drift monitoring, rollback and retraining owner | Not assigned |
| Site acceptance reviewer and evidence links | Not approved |

A file hash checks consistency with the configured artifact; it does not establish who trained the artifact or that it is safe to load. Only load weights from trusted sources. A model can have the right label names and still perform poorly. This card must accompany actual measurements before a field performance claim.
