# Security and responsible use

Version 0.2 is a shadow-pilot service. It has no physical traffic or vehicle outputs.

## Trust boundaries

- External sensor credentials authorize only one configured site/sensor. Reader and operator credentials are separate. All credentials must be random ASCII strings of at least 32 characters.
- API ingestion validates payload sizes, schema, freshness, monotonic acquisition timestamps and observation IDs. An authenticated sender can still lie about its scene; sensor/device integrity is an integrator responsibility.
- HTTP is intended for loopback development or a managed TLS gateway. MQTT uses CA validation and optional client certificates; plaintext is restricted to explicit loopback laboratory use.
- YOLO weights require a matching configured SHA-256 and requested class labels. Hash matching is not a substitute for a trusted model source.
- Do not load untrusted model weights, expose tokens in URLs, commit secrets, or publish private species locations.

## Data and availability

The service retains event metadata, observation digests/timestamps and operator-hold audit records. It does not retain raw video. Restrict access to sensitive locations, local database files and backups. Holds persist; sensor coverage starts unknown after a reboot. Expired messages never imply a clear road.

Protect the service with network access controls, TLS, per-client gateway rate limits, storage/power monitoring, patch management and managed credentials before connecting remote devices. Application-level limits do not replace a perimeter or a device security design. Read-only endpoints and API schema metadata are not an SSO implementation.

## Reporting

Use a private security reporting channel on GitHub if the repository owner has enabled it. Do not put credentials, private recordings or exploitable deployment details in a public issue. This repository does not promise a security response SLA.

## Safety and health boundaries

The signal simulator is not a certified controller. Reference timings are test values, not field instructions. Failures surface as unavailable monitoring, not guaranteed animal absence. A site's independently approved hardware system owns actual fallback behavior.

Surface temperature metadata is non-diagnostic. Vaccination helpers remain planning arithmetic, not medical recommendations, animal-treatment instructions or automated interventions. No disease-detection effectiveness or collision-reduction evidence is claimed.
