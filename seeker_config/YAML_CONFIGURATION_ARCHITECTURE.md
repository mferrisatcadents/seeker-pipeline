# YAML Configuration-Based Parsing in the Seeker Pipeline

This explains the YAML pattern implied by the Epic 1 backlog stories
(**Unified YAML Configuration Loader**, **Mock Endpoint Server**, **Cisco
Vendor YAML Configuration**) and how the accompanying `seeker_config`
module implements it. It's the reference for "why does the pipeline load
config this way" the next time a new vendor (or a reviewer) needs an answer.

## 1. The core idea: configuration as data, code as behavior

Every vendor collector — Cisco, Juniper, Palo Alto, Fortinet, Aruba — does
the same three things: fetch from a source, tag the result with a
confidence tier, and hand it to the same Phase 5 normalization engine. What
differs per vendor is *data*, not *logic*: endpoint URLs, which ingestion
phase (2A/2B/2C/2D) a source belongs to, and what confidence tier it's
assigned.

The backlog encodes this directly: the Cisco YAML Configuration story's
AC-04 requires that "no hardcoded URLs, credentials, or tier values exist
in any collector file." The collector is one piece of code; the vendor is
one YAML file. Add a sixth vendor by writing a new YAML file, not by
copy-pasting a Python module.

## 2. Why `!include` instead of one flat file per vendor

Several settings are identical across all five vendors — the OAuth2 flow
shape, the canonical phase list, the confidence tier definitions. Without
sharing, every vendor's YAML would repeat them, and a change to (say) the
confidence tier list would require five simultaneous edits that are easy
to let drift out of sync.

`!include` solves this by letting a top-level vendor file reference a
shared sub-config in place of inlining it:

```yaml
vendor: cisco
auth: !include _shared/auth.yaml
phases: !include _shared/phases.yaml
sources:
  - name: cisco_openvuln_api
    type: api
    ingestion_phase: "2A"
    confidence_tier: 1
```

At load time, `!include _shared/auth.yaml` is replaced with the fully
parsed contents of that file. The loader (`seeker_config/loader.py`)
implements this with a custom PyYAML constructor registered via
`yaml.add_constructor`, exactly as called out in the story's Technical
Notes. Two properties fall out of this design that the acceptance criteria
depend on directly:

- **Include paths are relative to the referencing file, not the working
  directory.** A shared file can be included from vendor configs that live
  in different directories without every vendor needing to know where
  `_shared/` sits relative to *itself* versus relative to wherever the
  process happens to be invoked from.
- **Resolution is recursive.** An included file can itself use `!include`
  (e.g. a shared `auth.yaml` that includes a `retry_policy.yaml`), and each
  level resolves relative to its own directory.

## 3. Statelessness between vendor loads (AC-03)

The story is explicit that "keys from one vendor do not bleed into
another" and that the loader must have "no shared mutable state." This
matters because a single pipeline run loads all five vendor configs in the
same process — Python object identity bugs here (e.g. two configs
accidentally sharing a reference to the same shared-sub-config dict) would
be the kind of failure that only shows up as a subtle, hard-to-reproduce
data quality issue days later.

`seeker_config` avoids this by never caching a loaded config or reusing a
loader instance across calls. Every call to `load_vendor_config()` builds
a fresh `SafeLoader` subclass and parses a fresh copy of every file it
touches — including shared sub-configs, which are *re-parsed*, not
memoized, on every include. That trades a small amount of redundant
parsing (sub-configs are small) for a hard guarantee: two vendors loaded
in the same process can never share a mutable object.

## 4. Validation: two layers, one exception type

The loader answers "did the YAML parse and did all includes resolve?" It
deliberately does *not* answer "is this a *valid* Cisco config?" — that's
a separate concern, split out so the loader stays a general-purpose YAML
tool and the vendor-specific rules live in one place: `validation.py` plus
`schemas/vendor_config.schema.json`.

1. **JSON Schema shape check** — catches structural problems: a source
   missing a required field, a `type` value that isn't one of the known
   source types (`api`, `rss`, `html`, `portal`, `csaf`, `specialized`).
2. **Business rules** — a small set of checks (confidence tier must be an
   integer 1–4) expressed directly in Python for a clearer error message
   than the generic schema violation text would give.

Both layers raise the same `ConfigValidationError`, carrying the offending
field path and value, per AC-04 ("a `ConfigValidationError` is raised with
the field name and invalid value; pipeline startup is aborted"). A missing
`!include` target is a different failure mode — the file genuinely doesn't
exist, not "exists but is wrong" — so it stays a `FileNotFoundError`
subclass (`IncludeResolutionError`) rather than reusing
`ConfigValidationError`, matching the story's literal AC-02 wording.

## 5. The standalone validator CLI

The Epic 1 developer setup checklist calls for `scripts/validate_yaml.py`
as a tool separate from the pipeline's own startup validation — something
a developer runs by hand while drafting a new vendor's YAML, before ever
wiring it into a collector. It does exactly what `load_vendor_config` +
`validate_config` do internally, but as a CLI with a clean exit code:

```bash
python scripts/validate_yaml.py examples/cisco.yaml
# OK: 'examples/cisco.yaml' resolved and validated (cisco)
```

## 6. What this sets up for the Mock Endpoint Server

The Mock Endpoint Server story (also Epic 1) needs collectors to run
against local fixtures instead of live vendor endpoints. Because every
collector already reads its target URL from the resolved YAML config
rather than a hardcoded constant, pointing a collector at the mock server
is a config change, not a code change: swap the `url` field in a
test-scoped vendor config (or override it via a `!include`-shared
`test_endpoints.yaml`) to `http://localhost:<port>/<fixture-route>`. No
change to `seeker_config` itself is needed — this is the payoff of keeping
"vendor-specific" strictly in YAML and "how to load/validate config"
strictly in code.

## 7. Source layout

```
seeker_config/
  loader.py        # !include resolution, stateless per call
  validation.py     # JSON Schema + business-rule checks
  exceptions.py     # ConfigValidationError, IncludeResolutionError
  schemas/vendor_config.schema.json
examples/
  cisco.yaml, juniper.yaml    # top-level vendor configs
  _shared/auth.yaml, phases.yaml
scripts/validate_yaml.py
tests/test_loader.py          # one test per acceptance criterion
```

See `README.md` for install and usage instructions.
