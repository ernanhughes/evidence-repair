"""Stable artifact helpers.

Runs are useful only when the records can be compared later. These helpers keep
JSON serialization deterministic enough for fingerprints, tests, and docs.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any


IGNORED_SNAPSHOT_PARTS = {".git", "__pycache__", ".pytest_cache", ".ruff_cache"}


def _json_default(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return value.as_posix()
    return str(value)


def stable_json(value: Any) -> str:
    """Return deterministic JSON for records and fingerprints."""

    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    )


def fingerprint(value: Any) -> str:
    """Return a SHA-256 fingerprint for a JSON-compatible value."""

    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def file_fingerprint(path: Path) -> str:
    """Return a SHA-256 fingerprint for file bytes."""

    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    """Write a deterministic JSON artifact with a trailing newline."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(value) + "\n", encoding="utf-8")


def repository_snapshot(root: Path) -> dict[str, str]:
    """Fingerprint every ordinary file under a repository root."""

    resolved_root = root.resolve()
    rows: dict[str, str] = {}

    for path in sorted(resolved_root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in IGNORED_SNAPSHOT_PARTS for part in path.parts):
            continue
        relative = path.relative_to(resolved_root).as_posix()
        rows[relative] = file_fingerprint(path)

    return rows


def workspace_fingerprint(root: Path) -> str:
    """Fingerprint the current file-level state of a workspace."""

    return fingerprint(repository_snapshot(root))
