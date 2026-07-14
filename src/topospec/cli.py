"""topospec CLI — validate graphs, run calibration/gate/grid experiments.

Usage:
  topospec validate <graph.json> [...]
  topospec calibrate --config configs/calibration_a0.yaml [--smoke]
  topospec gate      --config configs/gate.yaml
  topospec grid      --config configs/grid_phase_b.yaml
  topospec info
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="topospec")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_val = sub.add_parser("validate", help="validate SpectrumGraph JSON files")
    p_val.add_argument("paths", nargs="+")

    for name in ("calibrate", "gate", "grid"):
        p = sub.add_parser(name)
        p.add_argument("--config", required=True)
        if name == "calibrate":
            p.add_argument("--smoke", action="store_true",
                           help="tiny fast run; allows dirty git tree")

    sub.add_parser("info", help="print package/environment info")

    args = parser.parse_args(argv)

    if args.cmd == "validate":
        from topospec.graphs.serializers.json_io import load_graph
        from topospec.graphs.validate import SchemaError, validate_graph

        rc = 0
        for path in args.paths:
            try:
                g = load_graph(path)
                validate_graph(g)
                print(f"OK   R{g.level} {g.building_id}  {path}")
            except (SchemaError, KeyError, ValueError) as exc:
                print(f"FAIL {path}: {exc}", file=sys.stderr)
                rc = 1
        return rc

    if args.cmd == "info":
        import numpy
        import scipy
        import torch

        import topospec

        print(f"topospec {topospec.__version__} (schema {topospec.SCHEMA_VERSION})")
        print(f"numpy {numpy.__version__} | scipy {scipy.__version__} | "
              f"torch {torch.__version__} (cuda={torch.cuda.is_available()})")
        return 0

    from topospec.experiments.config import load_config

    cfg, sha = load_config(args.config)
    if args.cmd == "calibrate":
        from topospec.experiments.runner import run_calibration

        return run_calibration(cfg, sha, args.config, smoke=args.smoke)
    if args.cmd == "gate":
        from topospec.experiments.runner import run_gate

        return run_gate(cfg, sha, args.config)
    if args.cmd == "grid":
        from topospec.experiments.runner import run_grid

        return run_grid(cfg, sha, args.config)
    return 1


if __name__ == "__main__":
    sys.exit(main())
