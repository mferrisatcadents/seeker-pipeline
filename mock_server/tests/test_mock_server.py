"""
Tests mirror the Mock Endpoint Server story's acceptance criteria.

Run with: pytest tests/test_mock_server.py -v
"""

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mock_server import create_app

BASE_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture()
def client():
    app = create_app(
        manifest_path=BASE_DIR / "routes.yaml",
        fixtures_root=BASE_DIR / "fixtures",
    )
    app.testing = True
    return app.test_client()


def test_ac01_binds_and_serves_each_fixture_route(client):
    resp = client.get("/cisco/openvuln/advisories")
    assert resp.status_code == 200
    assert resp.content_type.startswith("application/json")
    assert b"cisco-sa-20260901-example" in resp.data

    resp = client.get("/nvd/cve")
    assert resp.status_code == 200
    assert b"CVE-2026-00001" in resp.data

    resp = client.get("/pan/advisory.rss")
    assert resp.status_code == 200
    assert resp.content_type.startswith("application/rss+xml")


def test_ac02_collector_style_json_parse_round_trip(client):
    import json

    resp = client.get("/nvd/cve")
    parsed = json.loads(resp.data)
    # Same shape a live NVD API run would hand the collector.
    assert parsed["totalResults"] == 1
    assert parsed["vulnerabilities"][0]["cve"]["id"] == "CVE-2026-00001"


def test_ac03_undefined_route_returns_404_and_server_stays_up(client):
    resp = client.get("/not/a/real/route")
    assert resp.status_code == 404

    # Server keeps serving other routes afterward — no crash, no lingering state.
    resp = client.get("/cisco/openvuln/advisories")
    assert resp.status_code == 200


def test_ac04_configured_delay_is_applied(client):
    start = time.monotonic()
    resp = client.get("/cisco/eox/slow")  # configured for 800ms in routes.yaml
    elapsed_ms = (time.monotonic() - start) * 1000

    assert resp.status_code == 200
    assert elapsed_ms >= 750  # small tolerance below the configured 800ms


def test_ac04_runtime_delay_override_from_dashboard_api(client):
    # Route starts with 0ms delay; the dashboard's delay endpoint should be
    # able to change that without touching routes.yaml or restarting.
    set_resp = client.post(
        "/_dashboard/api/routes/cisco/openvuln/advisories/delay",
        json={"delay_ms": 300},
    )
    assert set_resp.status_code == 200

    start = time.monotonic()
    resp = client.get("/cisco/openvuln/advisories")
    elapsed_ms = (time.monotonic() - start) * 1000

    assert resp.status_code == 200
    assert elapsed_ms >= 250
