# Vehicle and navigation integration

Version 0.2 exposes authenticated JSON advisories and configured hotspot GeoJSON. See [the full integration contract](company_integration.md) and [OpenAPI](../schemas/openapi.json).

Vehicles or navigation products can develop an advisory consumer using `examples/consume_events.py`. Preserve site identifiers, issuance/expiry, unknown-coverage status and event deduplication. Do not translate the simulated phase into a vehicle braking or traffic-lamp command.

No standardized SAE J2735, ETSI ITS, C-V2X, DSRC, OEM CAN, ADAS braking, map-provider partnership or production automotive security stack is implemented. A company's authorized gateway must implement the protocol, security credentials, timing guarantees and certification obligations applicable to its product.

A numeric risk index is an uncalibrated heuristic, not a collision probability or a recommended automatic driving speed. Optional advisory speeds must come from the responsible site's engineering process.
