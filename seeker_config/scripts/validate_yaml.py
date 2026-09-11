#!/usr/bin/env python3
"""
scripts/validate_yaml.py

Standalone YAML Validator Utility (Epic 1 Developer Setup Checklist item).

Validates a vendor config against the JSON schema and verifies that every
`!include` path it references resolves to a real file. Exits 0 on success;
exits 1 with a descriptive message on any failure.

Usage:
    python scripts/validate_yaml.py examples/cisco.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running this script directly from a `scripts/` dir sitting next to
# the package, without requiring the package to be pip-installed first.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from seeker_config import ConfigValidationError, load_vendor_config, validate_config
from seeker_config.exceptions import IncludeResolutionError


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config_path", help="Path to the vendor's top-level YAML config")
    args = parser.parse_args()

    try:
        config = load_vendor_config(args.config_path)
    except IncludeResolutionError as exc:
        print(f"FAIL: unresolved !include — {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    try:
        validate_config(config)
    except ConfigValidationError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print(f"OK: '{args.config_path}' resolved and validated ({config.get('vendor')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
