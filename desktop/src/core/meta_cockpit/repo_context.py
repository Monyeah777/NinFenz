"""Repository-root discovery without machine-specific absolute paths."""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent


def repository_root() -> Path:
    """Return the NF checkout root.

    ``NF_REPO_ROOT`` is an explicit test/deployment override. Otherwise the
    package location is authoritative: core/meta_cockpit -> repository root.
    """
    override = os.environ.get("NF_REPO_ROOT")
    return Path(override).resolve() if override else PACKAGE_ROOT.parents[3]


def implementation_files() -> tuple[str, ...]:
    """All versioned cockpit code, contracts and formal notes.

    Human review records are deliberately excluded: signing one must not alter
    the runtime identity it is reviewing.
    """
    suffixes = {".py", ".json", ".md"}
    return tuple(
        sorted(
            path.name
            for path in PACKAGE_ROOT.iterdir()
            if path.is_file()
            and path.suffix in suffixes
            and path.name != "human_review_record.json"
        )
    )
