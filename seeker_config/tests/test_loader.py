"""
Tests are written to mirror the Unified YAML Configuration Loader story's
acceptance criteria one-for-one, so a failing AC is easy to spot.

Run with:  pytest tests/test_loader.py -v
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from seeker_config import ConfigValidationError, load_vendor_config, validate_config
from seeker_config.exceptions import IncludeResolutionError

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def test_ac01_includes_resolved_and_merged():
    config = load_vendor_config(EXAMPLES / "cisco.yaml")
    assert config["vendor"] == "cisco"
    # !include targets are fully resolved, not left as tag markers
    assert config["auth"]["type"] == "oauth2"
    assert "PHASE_EOVS" in config["phases"]["canonical_phases"]
    assert len(config["sources"]) == 3


def test_ac02_missing_include_raises_filenotfounderror(tmp_path):
    bad_config = tmp_path / "broken.yaml"
    bad_config.write_text("vendor: broken\nauth: !include does_not_exist.yaml\n")

    with pytest.raises(FileNotFoundError) as exc_info:
        load_vendor_config(bad_config)

    assert "does_not_exist.yaml" in str(exc_info.value)
    assert isinstance(exc_info.value, IncludeResolutionError)


def test_ac03_configs_isolated_across_sequential_loads():
    cisco = load_vendor_config(EXAMPLES / "cisco.yaml")
    juniper = load_vendor_config(EXAMPLES / "juniper.yaml")

    assert cisco["vendor"] == "cisco"
    assert juniper["vendor"] == "juniper"
    # Cisco-only source names must not leak into Juniper's resolved config
    juniper_source_names = {s["name"] for s in juniper["sources"]}
    assert "cisco_openvuln_api" not in juniper_source_names
    # Mutating one loaded config's shared sub-config must not affect the other
    cisco["auth"]["scopes"].append("mutated-in-place")
    juniper_again = load_vendor_config(EXAMPLES / "juniper.yaml")
    assert "mutated-in-place" not in juniper_again["auth"]["scopes"]


def test_ac04_unknown_source_type_raises_config_validation_error(tmp_path):
    bad_config = tmp_path / "bad_type.yaml"
    bad_config.write_text(
        "vendor: bad\n"
        "sources:\n"
        "  - name: mystery_source\n"
        "    type: carrier_pigeon\n"
        "    ingestion_phase: \"2A\"\n"
        "    confidence_tier: 1\n"
    )
    config = load_vendor_config(bad_config)

    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config(config)

    assert "type" in exc_info.value.field
    assert exc_info.value.value == "carrier_pigeon"


def test_ac04_out_of_range_confidence_tier_raises_config_validation_error(tmp_path):
    bad_config = tmp_path / "bad_tier.yaml"
    bad_config.write_text(
        "vendor: bad\n"
        "sources:\n"
        "  - name: too_confident\n"
        "    type: api\n"
        "    ingestion_phase: \"1\"\n"
        "    confidence_tier: 7\n"
    )
    config = load_vendor_config(bad_config)

    with pytest.raises(ConfigValidationError) as exc_info:
        validate_config(config)

    assert "confidence_tier" in exc_info.value.field
    assert exc_info.value.value == 7
