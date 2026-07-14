"""Run manifests + registry integrity (results/CLAUDE.md; CLAUDE.md §Integrity)."""

import json

import pytest

from topospec.experiments.manifest import (
    DirtyTreeError,
    create_run,
    finalize_run,
    git_info,
)
from topospec.experiments.registry import append_entry, read_entries


def test_create_and_finalize_run(tmp_path, monkeypatch):
    # force a "dirty" git answer to exercise the smoke path deterministically
    run_dir = create_run(
        experiment="unit",
        config_path="configs/x.yaml",
        config_sha256="ab" * 32,
        seed=1,
        smoke=True,
        runs_root=tmp_path,
    )
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["status"] == "running"
    assert manifest["seed"] == 1
    assert manifest["smoke"] is True
    assert manifest["config_sha256"] == "ab" * 32
    final = finalize_run(run_dir, "completed", {"n_cells": 3})
    assert final["status"] == "completed"
    assert final["n_cells"] == 3
    assert "ended_utc" in final


def test_dirty_tree_refused_for_registered_runs(tmp_path, monkeypatch):
    import topospec.experiments.manifest as m

    monkeypatch.setattr(m, "git_info", lambda: {"sha": "deadbeef", "dirty": True})
    with pytest.raises(DirtyTreeError):
        m.create_run(
            experiment="unit",
            config_path="c.yaml",
            config_sha256="0" * 64,
            seed=0,
            smoke=False,
            runs_root=tmp_path,
        )
    # smoke is allowed on a dirty tree
    run_dir = m.create_run(
        experiment="unit",
        config_path="c.yaml",
        config_sha256="0" * 64,
        seed=0,
        smoke=True,
        runs_root=tmp_path,
    )
    assert run_dir.exists()


def test_registry_append_only_roundtrip(tmp_path):
    path = tmp_path / "registry.jsonl"
    append_entry({"run_id": "r1", "status": "completed"}, registry_path=path)
    append_entry({"run_id": "r2", "status": "failed"}, registry_path=path)
    entries = read_entries(registry_path=path)
    assert [e["run_id"] for e in entries] == ["r1", "r2"]
    with pytest.raises(ValueError):
        append_entry({"status": "completed"}, registry_path=path)


def test_git_info_shape():
    info = git_info()
    assert "sha" in info and "dirty" in info
