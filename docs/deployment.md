# Deployment and operations

## Supported deployment shape

The pilot is one Python service and one local SQLite journal per instance. Multiple sites can run in the same instance, with independent state. Separate roadside computers should use separate databases and publish advisories to a company's aggregation layer. A distributed coordinator, high availability, split-brain prevention, cloud fleet manager and OTA updater are not included.

Local verification used Linux x86-64 and Python 3.12. CI declares Python 3.11–3.13 on Linux. Linux ARM64, Jetson, Raspberry Pi, Windows, macOS, camera firmware and hardware acceleration require their own validation. The absence of a root-filesystem write requirement does not certify compatibility with every immutable OS.

## Install and configuration

Follow the README. The core service does not import camera/YOLO dependencies until a configured capture worker starts. Install `.[vision]` only for a chosen camera/model toolchain and `.[mqtt]` only when enabling MQTT. The default container uses external sensor ingestion and no camera devices.

All paths in YAML resolve relative to the YAML file. Pin the application commit, Python environment, model/dataset hashes and site config in the release record. JSON configuration follows the same schema and can also be loaded by the YAML reader.

Sample files describe synthetic sites. Replace coordinates, species, coverage, weather envelope, times and trust material. `validate` checks schema and resolves paths; camera model existence/hash/classes are checked at worker startup. A failed required camera appears as unavailable with a sanitized capture error in `/status`.

## Container

Set the README's credentials, then:

```bash
docker compose config
docker compose up --build -d
docker compose logs --tail=100 app
```

The compose service runs as UID 10001, drops capabilities, uses a read-only root filesystem, binds its port only to localhost, and mounts a named data volume. The container healthcheck tests process responsiveness; `/readyz` additionally tests sensor coverage. No real observations means readiness returns 503 even though the process is healthy.

The default Dockerfile does not include Ultralytics, camera libraries or hardware drivers. Derive a pinned device-specific image and test its camera/GPU access. Mount trusted model/certificate/config files read-only and grant only necessary device access; do not use a privileged container. Set device buffers and acquisition-time handling using the manufacturer's supported interface.

Docker and a real MQTT broker were not available for the local development checks. The workflow includes a container build/start check; its result must be reviewed separately. A deployment template is not evidence of a successful field installation.

## systemd

`deploy/wildlife.service` is a reviewable example, not an automatically installed system service.

Create a dedicated `wildlife` user/group, install the application and venv under `/opt/wildlife`, put the configuration at `/etc/wildlife/pilot.yaml`, and set its `database_path` to `/var/lib/wildlife/events.sqlite3`. Create that directory with ownership for the service. Put credentials in a root-owned mode-0600 `/etc/wildlife/secrets.env` file.

Review device access if adding cameras. Copy the unit to `/etc/systemd/system/`, reload systemd, and start only after validating configuration. Monitor readiness independently of process liveness. Do not add extra Uvicorn workers or run the old separate camera-loop command.

## Authentication and transport

Use distinct, random reader/operator/scoped-sensor credentials. The example `token` command generates them locally. The operator credential is optional; hold writes are disabled without it. The service has no default keys.

For remote clients, expose the service only through a managed HTTPS/mTLS gateway with rate limits, timeouts, access logs and allowlists appropriate to the site's trust model. The Python server itself is not an enterprise perimeter. Do not send bearer tokens over plain HTTP beyond an isolated loopback development session. No wildcard CORS policy is installed.

MQTT supports TLS CA validation, optional client certificates, username/password values loaded from named environment variables, reconnect backoff, a bounded client queue, and QoS 1. Certificate/key files must be paired. Plaintext MQTT is accepted only for explicit loopback lab configuration. Certificate expiry, broker ACLs, account rotation and certificate provisioning are integrator tasks. The transport does not produce automotive signed safety messages.

## Monitoring and recovery

Monitor `/readyz`, required/optional sensor faults, capture errors, clock/storage/worker fault flags, overdue occupancy, ingestion rejections and MQTT delivery lag. A site can have a recent wildlife warning while coverage is degraded. Counters reset on process restart; persisted events do not.

Stop and investigate camera faults, then restart after restoring the source. Video EOF is terminal. External sensors recover automatically when fresh healthy observations arrive. The service does not loop old recordings as live wildlife.

A wall-clock step over two seconds latches a fault; correct time sync and restart. A database error also latches a fault. A persistent operator hold can be released only with the operator key and an audit reason. Release does not skip the simulator's remaining clearance logic.

SQLite pruning runs every 30 seconds: configurable age retention and maximum observation/event rows. Row limits are soft between pruning ticks. Deleted pages may remain allocated for reuse, so measure actual peak disk/WAL use and set disk monitoring. Outstanding messages can be evicted by TTL/retention/row limits; this is not a guaranteed-delivery life-safety channel.

No frames are stored by the service. The journal includes IDs, timestamp/digest watermarks, site/species advisories and hold audit reasons. Treat sensitive species locations and operator notes as controlled data. Do not put personal data in hold reasons.

## Backup, upgrade and rollback

Use SQLite's online backup API or stop the service before copying a database. Copying only the database file while WAL writes are active can produce an incomplete backup. A sample stopped-service backup command is an ordinary file copy after confirming the process is stopped.

Before upgrading, record the old commit, Python dependency inventory, model/config hashes and database schema version; create a recoverable backup. Validate new config and run software/bench replay tests. Stop the old instance before starting the new one. Schema version 1 is currently the only supported version; unknown future versions are refused.

Rollback the application/config/model and restore the matching backup while stopped. Restoring older data can lose newer audit entries and requires consumer cursors to be reset/reconciled. After any restart, sensor state begins unknown; restored journal data never proves current road clearance.
