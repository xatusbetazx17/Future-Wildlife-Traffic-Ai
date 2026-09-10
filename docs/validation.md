# Software validation evidence

This report describes local checks for the version 0.2 pilot implementation. It is not a field evaluation or a certification.

## Completed locally

| Check | Result |
| --- | --- |
| Automated tests | **88 passed**, 0 failures, 0 errors, 0 skipped |
| Randomized signal sequences | 10 deterministic seeds × 1,000 state updates; transitions and minimum clearances checked |
| Real process and HTTP socket | Server starts, accepts scoped observations, watchdog expires coverage without status polling, and exits cleanly |
| API security | Reader/operator/sensor separation, replay/duplicate handling, size limits, rate limits and invalid inputs tested |
| Persistence | Restarted holds, durable timestamp watermarks, bounded rows and exclusive database ownership tested |
| Video | Generated three-frame AVI reaches EOF and terminates; motion cannot establish wildlife coverage |
| Detector integration | Missing model/hash/class failures tested; YOLO class contract uses a test double |
| MQTT | Outbox retry/exception and TLS/QoS/expiry client contract tested with test doubles |
| Model-free demonstration | Wildlife crossing, sensor outage and recovery; [recorded simulation](simulation-result.json) |
| Evaluation arithmetic | Counts, missing denominators, latency, confidence interval and synthetic provenance tested; [illustrative result](evaluation-synthetic-result.json) |
| Configuration | Pilot, multi-site, camera-template and legacy sample schemas load successfully |
| Static checks | Ruff lint, formatting, Python compilation, dashboard JavaScript syntax and git whitespace checks |
| Packaging | Wheel and source distribution built; dashboard bundled in wheel and guides/configs in source archive |

The environment was **Linux x86-64, Python 3.12.14**. Dependency versions and machine-readable test totals are in [test-environment.json](test-environment.json). The run emitted two upstream Starlette/HTTPX/AnyIO deprecation warnings; no project test failed.

The test suite does not download a wildlife model, train a network or measure its detection accuracy. The generated video is a software fixture, not representative road footage. MQTT test doubles do not prove broker/network interoperability.

## Not verified locally

- Real wildlife inference, thermal/radar hardware, sensor calibration or independent scene-quality checks.
- Night/weather/species/distance performance, public-road behavior, human response or collision outcomes.
- Live MQTT broker, TLS certificate deployment or actual automotive V2X hardware.
- Docker/systemd execution and physical camera access on a deployment host.
- ARM64/Jetson/Raspberry Pi/Windows/macOS, GPU acceleration or every Linux distribution.
- Visual rendering in a full browser, penetration testing, dependency vulnerability audit or an operational security assessment.
- A certified signal controller, road-authority approval or a field safety case.

The repository includes a Linux Python 3.11–3.13 CI matrix and a container build/start job. Those are declared gates; check the actual GitHub Actions result for the pushed commit rather than treating this local report as a CI pass.

## Reproduce

```bash
python -m pip install -e ".[test,mqtt]" opencv-python-headless
python -m pytest -q
python -m ruff check src tests examples
python -m ruff format --check src tests examples
python -m src.main --config configs/pilot.yaml validate
python -m src.main demo
python -m src.evaluation examples/evaluation.synthetic.json
python -m build
```

A company can replace the evaluation fixture with independently labeled field windows and build a measured pilot evidence package using [the field-validation guide](field_validation.md). Until then, performance remains unestablished.
