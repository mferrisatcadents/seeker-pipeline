"""
Unified YAML Configuration Loader (CAD-XXX, Epic 1).

Resolves `!include` directives inside vendor YAML configs so that shared
sub-configs (auth.yaml, phases.yaml, confidence_tiers.yaml, ...) can be
referenced from any vendor's top-level file without duplication.

Design notes (mirrors the story's Technical Notes / ACs):

- Stateless between calls (AC-03): every call to `load_vendor_config`
  builds its own PyYAML Loader subclass and its own include-path stack.
  Nothing is cached at module scope, so loading Cisco then Juniper can
  never leak keys or partial state between the two.
- `!include` paths are resolved relative to the file that references them,
  not relative to the process's current working directory or the original
  top-level config. This is what lets `examples/_shared/auth.yaml` be
  included from configs that live in different directories.
- A missing include raises the built-in `FileNotFoundError` (via
  `IncludeResolutionError`, a subclass) identifying the missing path
  (AC-02). No partial config is returned — the exception propagates before
  `yaml.load` produces a result.
- Include resolution is recursive: an included file may itself contain
  `!include` directives, resolved relative to *its own* directory.
"""

from __future__ import annotations

import pathlib
from typing import Any

import yaml

from .exceptions import IncludeResolutionError

INCLUDE_TAG = "!include"


def _make_loader_class() -> type[yaml.SafeLoader]:
    """
    Build a fresh SafeLoader subclass for a single top-level load.

    A new class (not a shared global one) is created per call so that the
    `!include` constructor's closure captures a fresh, call-local base
    directory rather than reusing state across separate `load_vendor_config`
    invocations. This is what guarantees AC-03 (config isolation) even
    though PyYAML's constructor registration API is otherwise class-global.
    """

    class _IncludeLoader(yaml.SafeLoader):
        pass

    def _include_constructor(loader: "_IncludeLoader", node: yaml.Node) -> Any:
        include_ref = loader.construct_scalar(node)
        current_dir = pathlib.Path(loader.name).resolve().parent
        target_path = (current_dir / include_ref).resolve()

        if not target_path.is_file():
            raise IncludeResolutionError(
                missing_path=str(include_ref),
                referenced_from=str(loader.name),
            )

        return _load_file(target_path)

    _IncludeLoader.add_constructor(INCLUDE_TAG, _include_constructor)
    return _IncludeLoader


def _load_file(path: pathlib.Path) -> Any:
    """
    Parse a single YAML file with its own fresh loader class, so nested
    `!include` directives resolve relative to *this* file's directory.
    """
    loader_cls = _make_loader_class()
    with open(path, "r", encoding="utf-8") as fh:
        # yaml.Loader.name is set from the stream; give it a real path so
        # the !include constructor above can resolve relative paths from it.
        return yaml.load(fh, Loader=_bind_name(loader_cls, str(path)))


def _bind_name(loader_cls: type[yaml.SafeLoader], name: str) -> Any:
    """
    Return a loader *factory* (what yaml.load expects for `Loader=`) that,
    when instantiated by PyYAML, has `.name` pre-set to `name` so relative
    `!include` paths resolve correctly even for in-memory streams.
    """

    def _factory(stream):
        instance = loader_cls(stream)
        instance.name = name
        return instance

    return _factory


def load_vendor_config(path: str | pathlib.Path) -> dict:
    """
    Load a vendor's top-level YAML config, resolving every `!include`
    directive (including nested ones) into a single merged config object.

    Args:
        path: path to the vendor's top-level YAML file, e.g.
              "examples/cisco.yaml".

    Returns:
        The fully resolved config as a plain dict.

    Raises:
        FileNotFoundError: the top-level path itself doesn't exist, or an
            `!include` directive (at any depth) points at a missing file
            (raised as IncludeResolutionError, a FileNotFoundError subclass).
    """
    top_level_path = pathlib.Path(path).resolve()
    if not top_level_path.is_file():
        raise FileNotFoundError(f"Vendor config not found: '{top_level_path}'")

    config = _load_file(top_level_path)
    return config if config is not None else {}
