"""Experiment configs — the ONLY way runs are parameterized (results/CLAUDE.md).

A config file + a git SHA fully determine a run. Configs are immutable once used;
variants are new files. `load_config` returns (dict, sha256-of-file-bytes).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

REQUIRED_KEYS = ("experiment", "seed")


def load_config(path: str | Path) -> tuple[dict, str]:
    p = Path(path)
    raw = p.read_bytes()
    cfg = yaml.safe_load(raw)
    if not isinstance(cfg, dict):
        raise ValueError(f"{p}: config must be a mapping")
    missing = [k for k in REQUIRED_KEYS if k not in cfg]
    if missing:
        raise ValueError(f"{p}: missing required config keys {missing}")
    return cfg, hashlib.sha256(raw).hexdigest()
