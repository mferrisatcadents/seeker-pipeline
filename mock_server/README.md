# mock_server

Local mock endpoint server for Seeker Pipeline collectors (Epic 1, Mock
Endpoint Server story). Serves fixture files at configured routes so
Phase 1/2 collectors can be developed and tested without hitting live
vendor endpoints or their rate limits.

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
python run.py                 # http://localhost:8089, dashboard at /
python run.py --port 9000     # different port
python run.py --debug         # Flask auto-reload while editing fixtures/routes.yaml
```

Open `http://localhost:8089/` for the dashboard: registered routes, an
inline delay override per route, a "test" button that fires the route and
previews the response, and a live-polling request log.

## Point a collector at it

Add or override a source's `url` in the vendor's YAML config (see the
`seeker_config` module) to `http://localhost:8089/<route>` — e.g.
`http://localhost:8089/cisco/openvuln/advisories`. No collector code change
is required; only the config value changes.

## Add a new mock route

Edit `routes.yaml`:

```yaml
routes:
  - vendor: fortinet
    path: /fortinet/psirt/advisories
    fixture: fortinet/psirt.rss
    content_type: application/rss+xml
    delay_ms: 0
```

Then drop the fixture file at `fixtures/fortinet/psirt.rss`. Restart the
server (or run with `--debug` for auto-reload) and the new route appears
in the dashboard automatically.

## Run the tests

```bash
pytest tests/test_mock_server.py -v
```

One test per acceptance criterion from the story: route binding and
fixture serving, collector-style JSON round-trip, 404-without-crash on an
undefined route, and both the manifest-configured delay and the
dashboard's runtime delay override.

## Layout

```
mock_server/
  app.py            # Flask app factory: fixture routes + dashboard + API
  config.py         # routes.yaml -> RouteConfig
  state.py          # in-memory request log + runtime delay overrides
  templates/
    dashboard.html  # single-page dashboard (no build step)
routes.yaml          # route manifest
fixtures/
  cisco/, nvd/, pan/ # sample fixture files
run.py               # CLI entry point
tests/test_mock_server.py
```

## Out of scope (per the story)

- Simulating authentication flows — fixtures are pre-authenticated payloads.
- Phase 2D SPA/headless-browser mocking — separate tooling, not this server.
