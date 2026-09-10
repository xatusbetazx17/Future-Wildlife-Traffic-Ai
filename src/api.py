import asyncio
import hmac
import json
import os
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse

from .config import AppConfig, load_config
from .hotspots import hotspots, risk
from .models import ManualHold, Observation
from .runtime import RateLimitError, Runtime


class BodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        chunks, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body = message.get("body", b"")
            size += len(body)
            if size > 65536:
                return await JSONResponse({"detail": "request exceeds 64 KiB"}, status_code=413)(
                    scope, receive, send
                )
            chunks.append(body)
            if not message.get("more_body", False):
                break
        consumed = False

        async def replay():
            nonlocal consumed
            if not consumed:
                consumed = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


def create_app(config: AppConfig | None = None, runtime: Runtime | None = None, background=True):
    @asynccontextmanager
    async def lifespan(app):
        cfg = config or (
            runtime.config
            if runtime
            else load_config(os.getenv("WILDLIFE_CONFIG", "data/sample_config.yaml"))
        )
        read_key = os.getenv(cfg.api_key_env, "")
        admin_key = os.getenv(cfg.admin_key_env, "")
        if len(read_key) < 32 or not read_key.isascii():
            raise RuntimeError(cfg.api_key_env + " must contain at least 32 characters")
        if admin_key and (
            len(admin_key) < 32 or not admin_key.isascii() or hmac.compare_digest(read_key, admin_key)
        ):
            raise RuntimeError("admin key must be distinct and at least 32 characters")
        sensor_keys = json.loads(os.getenv(cfg.sensor_keys_env, "") or "{}")
        if not isinstance(sensor_keys, dict):
            raise RuntimeError("sensor keys must be a JSON object mapping site/sensor to token")
        scope_set = {s.id + "/" + c.id for s in cfg.sites for c in s.sensors if c.kind == "external"}
        values = [read_key] + ([admin_key] if admin_key else [])
        for scope, key in sensor_keys.items():
            if (
                scope not in scope_set
                or not isinstance(key, str)
                or len(key) < 32
                or not key.isascii()
                or key in values
            ):
                raise RuntimeError(
                    "sensor credentials must be unique, at least 32 characters, and scoped to external sensors"
                )
            values.append(key)
        app.state.read_key, app.state.admin_key, app.state.sensor_keys = read_key, admin_key, sensor_keys
        rt = runtime or Runtime(cfg)
        app.state.runtime = rt
        workers = []
        ticker = None

        async def heartbeat():
            while True:
                try:
                    rt.tick()
                except sqlite3.Error:
                    rt.storage_fault = True
                except Exception:
                    rt.worker_fault = True
                await asyncio.sleep(cfg.tick_s)

        try:
            if background:
                from .capture import CaptureWorker

                for site in cfg.sites:
                    for sensor in site.sensors:
                        if sensor.kind != "external":
                            worker = CaptureWorker(rt, site, sensor)
                            workers.append(worker)
                            worker.thread.start()
                if cfg.mqtt.enabled:
                    from .comms import MqttPublisher, OutboxWorker

                    worker = OutboxWorker(rt, MqttPublisher(cfg.mqtt))
                    workers.append(worker)
                    worker.thread.start()
                ticker = asyncio.create_task(heartbeat())
            yield
        finally:
            if ticker:
                ticker.cancel()
                try:
                    await ticker
                except asyncio.CancelledError:
                    pass
            for worker in workers:
                worker.close()
            if runtime is None:
                rt.close()

    app = FastAPI(
        title="Wildlife Traffic Pilot", version="0.2.0", lifespan=lifespan, docs_url="/docs", redoc_url=None
    )
    app.add_middleware(BodyLimit)

    def token(request: Request):
        value = request.headers.get("authorization", "")
        if not value.startswith("Bearer ") or len(value) > 1024 or not value.isascii():
            raise HTTPException(401, "Bearer token required", headers={"WWW-Authenticate": "Bearer"})
        return value[7:]

    def viewer(request: Request, key=Depends(token)):
        if not (
            hmac.compare_digest(key, request.app.state.read_key)
            or (request.app.state.admin_key and hmac.compare_digest(key, request.app.state.admin_key))
        ):
            raise HTTPException(403, "not authorized")

    def admin(request: Request, key=Depends(token)):
        if not request.app.state.admin_key or not hmac.compare_digest(key, request.app.state.admin_key):
            raise HTTPException(403, "operator credential required")

    @app.exception_handler(sqlite3.Error)
    async def database_error(request, exc):
        request.app.state.runtime.storage_fault = True
        return JSONResponse({"detail": "journal unavailable; monitoring degraded"}, status_code=503)

    @app.get("/", include_in_schema=False)
    def dashboard():
        return FileResponse(Path(__file__).parent / "web" / "index.html")

    @app.get("/healthz")
    def health():
        return {"service": "running"}

    @app.get("/readyz")
    def ready(request: Request):
        data = request.app.state.runtime.status()
        good = all(s["monitoring_healthy"] and not s["manual_hold"] for s in data["sites"])
        return JSONResponse({"ready": good}, status_code=200 if good else 503)

    @app.get("/status", dependencies=[Depends(viewer)])
    def status(request: Request):
        return request.app.state.runtime.status()

    @app.get("/hotspots", dependencies=[Depends(viewer)])
    def hotspot_feed(request: Request):
        return hotspots(request.app.state.runtime)

    @app.get("/risk", dependencies=[Depends(viewer)])
    def point_risk(
        request: Request,
        lat: float = Query(ge=-90, le=90, allow_inf_nan=False),
        lon: float = Query(ge=-180, le=180, allow_inf_nan=False),
        at: datetime | None = None,
    ):
        try:
            return risk(request.app.state.runtime, lat, lon, at or datetime.now(timezone.utc))
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/events", dependencies=[Depends(viewer)])
    def events(
        request: Request,
        after: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        active_only: bool = True,
    ):
        rt = request.app.state.runtime
        entries = rt.store.events(rt.wall(), after, limit, active_only)
        return {
            "schema_version": 1,
            "events": entries,
            "next_cursor": entries[-1]["sequence"] if entries else after,
            "delivery": "at_least_once",
            "expired_events_excluded": active_only,
        }

    @app.post("/v1/observations")
    def observe(obs: Observation, request: Request, key=Depends(token)):
        rt = request.app.state.runtime
        expected = request.app.state.sensor_keys.get(obs.site_id + "/" + obs.sensor_id)
        if not expected or not hmac.compare_digest(key, expected):
            raise HTTPException(403, "credential is not authorized for this sensor")
        try:
            return rt.ingest(obs)
        except RateLimitError as exc:
            raise HTTPException(429, str(exc), headers={"Retry-After": "1"}) from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/v1/sites/{site_id}/hold", dependencies=[Depends(admin)])
    def hold(site_id: str, control: ManualHold, request: Request):
        try:
            request.app.state.runtime.set_hold(site_id, control.enabled, control.reason)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
        return {"site_id": site_id, "manual_hold": control.enabled, "physical_control": False}

    @app.get("/metrics", dependencies=[Depends(viewer)], response_class=PlainTextResponse)
    def metrics(request: Request):
        data = request.app.state.runtime.status()
        lines = [
            f"wildlife_observations_accepted_total {data['observations_accepted']}",
            f"wildlife_observations_rejected_total {data['observations_rejected']}",
            f"wildlife_mqtt_pending {data['mqtt_pending']}",
        ]
        for site in data["sites"]:
            lines.append(
                f'wildlife_monitoring_healthy{{site="{site["site_id"]}"}} {int(site["monitoring_healthy"])}'
            )
        return "\n".join(lines) + "\n"

    return app
