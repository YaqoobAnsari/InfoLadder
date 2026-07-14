"""Append-only results registry — results/registry.jsonl (results/CLAUDE.md).

One line per completed OR failed run. Lines are never edited or removed; a bad run is
superseded by a new line carrying `supersedes: <run_id>` and a reason.
"""

from __future__ import annotations

import json
from pathlib import Path

from topospec.experiments.manifest import REPO_ROOT

REGISTRY_PATH = REPO_ROOT / "results" / "registry.jsonl"


def append_entry(entry: dict, registry_path: Path | None = None) -> None:
    path = registry_path or REGISTRY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    if "run_id" not in entry or "status" not in entry:
        raise ValueError("registry entries require run_id and status")
    with open(path, "a") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")


def read_entries(registry_path: Path | None = None) -> list[dict]:
    path = registry_path or REGISTRY_PATH
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
