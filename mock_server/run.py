#!/usr/bin/env python3
"""
Run the Seeker Mock Endpoint Server.

    python run.py                  # default: port 8089, no auto-reload
    python run.py --port 9000
    python run.py --debug          # enable Flask's auto-reloader

Dashboard: http://localhost:<port>/
"""

from __future__ import annotations

import argparse

from mock_server import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8089)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--routes", default="routes.yaml")
    parser.add_argument("--fixtures", default="fixtures")
    args = parser.parse_args()

    app = create_app(manifest_path=args.routes, fixtures_root=args.fixtures)
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
