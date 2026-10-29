"""Metacognitive production cockpit.

The package exposes a deterministic, model-agnostic control surface for
single-turn method composition and bounded multi-turn production. Content
quality claims remain external to the cockpit: the runtime records method,
context and state provenance, but never turns those records into an internal
score or approval.
"""

from __future__ import annotations

__all__ = ["build_manifest", "produce"]


def produce(*args, **kwargs):
    from .cockpit_service import produce as run

    return run(*args, **kwargs)


def build_manifest(*args, **kwargs):
    from .meta_runtime_manifest import build

    return build(*args, **kwargs)
