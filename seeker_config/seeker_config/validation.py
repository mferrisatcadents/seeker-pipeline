"""
Validation for resolved vendor configs (AC-04 of the Unified YAML
Configuration Loader story, and the standalone `scripts/validate_yaml.py`
utility from the Epic 1 developer setup checklist).

Two layers, both surfaced as `ConfigValidationError` with the field name and
the invalid value so pipeline startup can abort with a precise message:

1. JSON Schema shape check (structure, enums, required fields) — catches
   "unknown source type" and structurally malformed configs.
2. A small set of business rules that JSON Schema expresses awkwardly or
   that need a friendlier error message than jsonschema's default
   (e.g. confidence tier range, expressed here for a clearer field path).
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import jsonschema

from .exceptions import ConfigValidationError

_DEFAULT_SCHEMA_PATH = (
    pathlib.Path(__file__).parent / "schemas" / "vendor_config.schema.json"
)

VALID_CONFIDENCE_TIERS = (1, 2, 3, 4)
VALID_SOURCE_TYPES = ("api", "rss", "html", "portal", "csaf", "specialized")


def _load_schema(schema_path: pathlib.Path | None = None) -> dict:
    path = schema_path or _DEFAULT_SCHEMA_PATH
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _field_path_from_jsonschema_error(error: jsonschema.ValidationError) -> str:
    """Turn a jsonschema error's absolute_path deque into a dotted field name."""
    parts = [str(p) for p in error.absolute_path]
    return ".".join(parts) if parts else "<root>"


def validate_config(config: dict, schema_path: pathlib.Path | None = None) -> None:
    """
    Validate a resolved vendor config. Raises ConfigValidationError on the
    first violation found; does not return a value on success.
    """
    schema = _load_schema(schema_path)
    validator = jsonschema.Draft7Validator(schema)

    errors = sorted(validator.iter_errors(config), key=lambda e: list(e.absolute_path))
    if errors:
        first = errors[0]
        field = _field_path_from_jsonschema_error(first)
        raise ConfigValidationError(field=field, value=first.instance, reason=first.message)

    # Business rules with friendlier, field-specific messages than the raw
    # jsonschema output would give (schema still catches these as a backstop).
    for idx, source in enumerate(config.get("sources", [])):
        _validate_source(source, index=idx)


def _validate_source(source: dict, index: int) -> None:
    tier = source.get("confidence_tier")
    if tier not in VALID_CONFIDENCE_TIERS:
        raise ConfigValidationError(
            field=f"sources[{index}].confidence_tier",
            value=tier,
            reason=f"must be one of {VALID_CONFIDENCE_TIERS}",
        )

    source_type = source.get("type")
    if source_type not in VALID_SOURCE_TYPES:
        raise ConfigValidationError(
            field=f"sources[{index}].type",
            value=source_type,
            reason=f"must be one of {VALID_SOURCE_TYPES}",
        )
