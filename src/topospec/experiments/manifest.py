"""Run manifests — every number traces to one (root CLAUDE.md §Integrity).

A manifest records: run_id, experiment, timestamps, git SHA (+dirty flag), config path
and sha256, seed, host, package versions. Registered (non-smoke) runs REFUSE a dirty
git tree unless the config sets allow_dirty: true (smoke tests only).
"""

from __future__ import annotations

import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


class DirtyTreeError(RuntimeError):
    pass


def git_info() -> dict:
    def run(*args: str) -> str | None:
        try:
            return subprocess.run(
                ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
            ).stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

    sha = run("rev-parse", "HEAD")
    # registry.jsonl is machine-appended by every completed run (append-only by
    # design) — its dirtiness between commits is expected and must not block the
    # next chained/overnight registered run
    status = run("status", "--porcelain", "--", ".", ":(exclude)results/registry.jsonl")
    return {
        "sha": sha or "NO-GIT",
        "dirty": bool(status) if status is not None else None,
    }


def package_versions() -> dict:
    out = {}
    for mod in ("numpy", "scipy", "sklearn", "torch", "networkx", "shapely"):
        try:
            out[mod] = __import__(mod).__version__
        except ImportError:
            out[mod] = None
    return out


def create_run(
    experiment: str,
    config_path: str,
    config_sha256: str,
    seed: int,
    smoke: bool = False,
    allow_dirty: bool = False,
    runs_root: Path | None = None,
) -> Path:
    """Create runs/<run_id>/ with manifest.json; returns the run directory."""
    git = git_info()
    if git["dirty"] and not (smoke or allow_dirty):
        raise DirtyTreeError(
            "git tree is dirty; registered runs require a clean tree "
            "(commit first, or use --smoke / allow_dirty for smoke tests only)"
        )
    ts = datetime.now(timezone.utc)
    run_id = f"{ts.strftime('%Y%m%dT%H%M%SZ')}-{experiment}-s{seed}" + (
        "-smoke" if smoke else ""
    )
    run_dir = (runs_root or REPO_ROOT / "runs") / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    manifest = {
        "run_id": run_id,
        "experiment": experiment,
        "started_utc": ts.isoformat(),
        "git": git,
        "config_path": str(config_path),
        "config_sha256": config_sha256,
        "seed": seed,
        "smoke": smoke,
        "host": platform.node(),
        "python": platform.python_version(),
        "packages": package_versions(),
        "status": "running",
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return run_dir


def finalize_run(run_dir: Path, status: str, extra: dict | None = None) -> dict:
    """Stamp final status ('completed' | 'failed') and end time into the manifest."""
    mpath = Path(run_dir) / "manifest.json"
    manifest = json.loads(mpath.read_text())
    manifest["status"] = status
    manifest["ended_utc"] = datetime.now(timezone.utc).isoformat()
    if extra:
        manifest.update(extra)
    mpath.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest
