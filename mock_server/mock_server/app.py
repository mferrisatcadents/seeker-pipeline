"""
Mock Endpoint Server (Epic 1, CAD-XXX).

create_app() builds a Flask app that:
  - serves a fixture file at each route declared in routes.yaml (AC-01)
  - returns the same bytes/content-type a collector would get from the real
    endpoint, so a collector configured against this server behaves
    identically to a live run (AC-02)
  - returns Flask's normal 404 for any undeclared route, and keeps serving
    everything else afterward (AC-03) — this falls out of Flask's default
    behavior; we don't override it, we just don't swallow it
  - applies a per-route delay (manifest default, or a runtime override set
    from the dashboard) before responding (AC-04)

The dashboard is a second, clearly-separated concern: it never touches
fixture bytes, it only reads route metadata and the request log.
"""

from __future__ import annotations

import pathlib
import time

from flask import Flask, Response, jsonify, render_template, request

from .config import RouteConfig, load_routes
from .state import DelayOverrides, RequestLogEntry, RequestLogStore, utc_timestamp

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent


def create_app(
    manifest_path: str | pathlib.Path = BASE_DIR / "routes.yaml",
    fixtures_root: str | pathlib.Path = BASE_DIR / "fixtures",
) -> Flask:
    app = Flask(__name__)
    fixtures_root = pathlib.Path(fixtures_root)

    routes = load_routes(manifest_path)
    routes_by_path = {r.path: r for r in routes}

    log_store = RequestLogStore()
    delays = DelayOverrides()
    for r in routes:
        delays.set(r.path, r.delay_ms)

    app.config["ROUTES"] = routes
    app.config["ROUTES_BY_PATH"] = routes_by_path
    app.config["LOG_STORE"] = log_store
    app.config["DELAYS"] = delays
    app.config["FIXTURES_ROOT"] = fixtures_root

    def _make_fixture_view(route: RouteConfig):
        fixture_path = fixtures_root / route.fixture_file

        def _view():
            start = time.monotonic()
            delay_ms = delays.get(route.path, route.delay_ms)
            if delay_ms:
                time.sleep(delay_ms / 1000.0)

            if not fixture_path.is_file():
                status = 500
                body = f"Fixture file missing on disk: {fixture_path}".encode()
            else:
                status = 200
                body = fixture_path.read_bytes()

            duration_ms = int((time.monotonic() - start) * 1000)
            log_store.record(
                RequestLogEntry(
                    timestamp=utc_timestamp(),
                    method=request.method,
                    path=route.path,
                    status=status,
                    duration_ms=duration_ms,
                    vendor=route.vendor,
                )
            )
            return Response(body, status=status, content_type=route.content_type)

        _view.__name__ = f"fixture_view_{route.vendor}_{route.path}"
        return _view

    for route in routes:
        app.add_url_rule(route.path, endpoint=route.path, view_func=_make_fixture_view(route))

    # --- Dashboard ---------------------------------------------------

    @app.route("/")
    def dashboard():
        return render_template("dashboard.html")

    @app.route("/_dashboard/api/routes")
    def api_routes():
        return jsonify(
            [
                {
                    "vendor": r.vendor,
                    "path": r.path,
                    "fixture": r.fixture_file,
                    "content_type": r.content_type,
                    "delay_ms": delays.get(r.path, r.delay_ms),
                }
                for r in routes
            ]
        )

    @app.route("/_dashboard/api/routes/<path:route_path>/delay", methods=["POST"])
    def api_set_delay(route_path: str):
        full_path = "/" + route_path
        if full_path not in routes_by_path:
            return jsonify({"error": f"unknown route '{full_path}'"}), 404
        payload = request.get_json(force=True, silent=True) or {}
        delay_ms = payload.get("delay_ms", 0)
        delays.set(full_path, delay_ms)
        return jsonify({"path": full_path, "delay_ms": delays.get(full_path, 0)})

    @app.route("/_dashboard/api/log")
    def api_log():
        return jsonify(log_store.recent())

    @app.route("/_dashboard/api/log/clear", methods=["POST"])
    def api_log_clear():
        log_store.clear()
        return jsonify({"cleared": True})

    return app
