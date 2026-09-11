"""
Loads the mock server's route manifest (routes.yaml) into typed RouteConfig
objects. Deliberately a plain PyYAML load (no !include) — this manifest is
test-only tooling data, not vendor collection config, so it doesn't need the
sharing/isolation guarantees `seeker_config` provides for that.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field

import yaml

DEFAULT_CONTENT_TYPES = {
    ".json": "application/json",
    ".html": "text/html",
    ".rss": "application/rss+xml",
    ".xml": "application/xml",
}


@dataclass
class RouteConfig:
    vendor: str
    path: str                 # URL path, e.g. "/cisco/openvuln/advisories"
    fixture_file: str         # relative to the fixtures root
    content_type: str
    delay_ms: int = 0

    @property
    def key(self) -> str:
        return self.path


def _infer_content_type(fixture_file: str) -> str:
    suffix = pathlib.Path(fixture_file).suffix.lower()
    return DEFAULT_CONTENT_TYPES.get(suffix, "application/octet-stream")


def load_routes(manifest_path: str | pathlib.Path) -> list[RouteConfig]:
    manifest_path = pathlib.Path(manifest_path)
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Route manifest not found: '{manifest_path}'")

    with open(manifest_path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    routes: list[RouteConfig] = []
    for entry in raw.get("routes", []):
        content_type = entry.get("content_type") or _infer_content_type(entry["fixture"])
        routes.append(
            RouteConfig(
                vendor=entry["vendor"],
                path=entry["path"],
                fixture_file=entry["fixture"],
                content_type=content_type,
                delay_ms=int(entry.get("delay_ms", 0)),
            )
        )
    return routes
