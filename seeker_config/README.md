# seeker_config

Unified YAML configuration loader for the Seeker Pipeline (CAD-XXX, Epic 1).
Resolves `!include` directives so vendor configs can share `auth.yaml`,
`phases.yaml`, and similar sub-configs without duplication, then validates
the resolved config against a JSON Schema.

Implements the acceptance criteria for:
- **Story: Unified YAML Configuration Loader**
- **Story: Cisco Vendor YAML Configuration** (and by extension, every other
  vendor's YAML config — the loader is vendor-agnostic)

See `YAML_CONFIGURATION_ARCHITECTURE.md` for the full explanation of why
this approach was chosen and how it fits the rest of the pipeline.

## Install

```bash
pip install -r requirements.txt
```

## Use

```python
from seeker_config import load_vendor_config, validate_config

config = load_vendor_config("examples/cisco.yaml")
validate_config(config)  # raises ConfigValidationError on failure
```

## Validate a config from the command line

```bash
python scripts/validate_yaml.py examples/cisco.yaml
```

## Layout

```
seeker_config/
  __init__.py          # public API: load_vendor_config, validate_config, exceptions
  loader.py             # !include resolution
  validation.py         # JSON Schema + business-rule validation
  exceptions.py         # ConfigValidationError, IncludeResolutionError
  schemas/
    vendor_config.schema.json
examples/
  cisco.yaml
  juniper.yaml
  _shared/
    auth.yaml
    phases.yaml
scripts/
  validate_yaml.py      # standalone CLI validator (Epic 1 dev setup checklist item)
tests/
  test_loader.py        # one test per acceptance criterion
```

## Wiring into the Mock Endpoint Server

Once the Mock Endpoint Server (separate Epic 1 story) is available, point a
vendor config's source `url` fields at `http://localhost:<port>/<fixture-route>`
in a test-only override — the loader itself is source-agnostic, so no change
to `loader.py` or `validation.py` is needed to run collectors against fixtures
instead of live vendor endpoints.
