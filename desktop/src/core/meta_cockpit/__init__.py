"""Metacognitive production cockpit.

The package exposes a deterministic, model-agnostic control surface for
single-turn method composition and bounded multi-turn production. Content
quality claims remain external to the cockpit: the runtime records method,
context and state provenance, but never turns those records into an internal
score or approval.
"""

from __future__ import annotations

from importlib import import_module

_LAZY_SUBMODULES = frozenset(
    {"build_atom_menu", "live_protocol", "mcp_context", "nf_metacognition"}
)

__all__ = [
    "build_atom_menu",
    "build_manifest",
    "live_protocol",
    "mcp_context",
    "nf_metacognition",
    "produce",
]


def __getattr__(name: str):
    """Load optional public submodules only when a consumer asks for them."""
    if name in _LAZY_SUBMODULES:
        module = import_module(f"{__name__}.{name}")
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(set(globals()) | set(__all__))


def produce(*args, **kwargs):
    from .cockpit_service import produce as run

    return run(*args, **kwargs)


def build_manifest(*args, **kwargs):
    from .meta_runtime_manifest import build

    return build(*args, **kwargs)
