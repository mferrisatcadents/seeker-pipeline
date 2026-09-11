"""
Exceptions raised by the Seeker vendor-config loader and validator.

FileNotFoundError is intentionally NOT re-wrapped here — the loader raises the
built-in FileNotFoundError directly (with a descriptive message identifying the
missing !include path) per AC-02 of the "Unified YAML Configuration Loader"
story. Only validation failures get a dedicated exception type.
"""

from __future__ import annotations


class ConfigValidationError(Exception):
    """
    Raised when a resolved vendor config fails schema or business-rule
    validation (AC-04): unknown source type, out-of-range confidence tier,
    or any other structural violation.

    Always carries the offending field path and the invalid value so the
    caller can log or surface a precise error without re-inspecting the
    whole config.
    """

    def __init__(self, field: str, value: object, reason: str):
        self.field = field
        self.value = value
        self.reason = reason
        super().__init__(f"Invalid config field '{field}' (value={value!r}): {reason}")


class IncludeResolutionError(FileNotFoundError):
    """
    Raised when an `!include` directive points at a path that does not exist.

    Subclasses FileNotFoundError so callers who only catch the built-in
    exception (per AC-02's literal wording) still catch this, while callers
    who want the extra context (which file referenced the missing include)
    can catch IncludeResolutionError specifically.
    """

    def __init__(self, missing_path: str, referenced_from: str):
        self.missing_path = missing_path
        self.referenced_from = referenced_from
        super().__init__(
            f"!include target not found: '{missing_path}' "
            f"(referenced from '{referenced_from}')"
        )
