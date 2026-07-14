"""Generate the versioned JSON Schema files for levels R0..R4 (plan Appendix B).

Regenerate after any schema change:
    $TOPOSPEC_PYTHON scripts/gen_schemas.py
The generated files are committed artifacts of the T5 toolkit (claim C1) and are
loaded by topospec.graphs.validate.json_schema_for_level.
"""

import json
from pathlib import Path

SPACE_KINDS = ["room", "door", "corridor"]
HIERARCHY_KINDS = ["corridor-cluster", "zone", "wing"]
EDGE_TAUS = ["wall", "door", "corridor-link"]
EDGE_DELTAS = ["both", "forward", "backward"]

OUT = Path(__file__).resolve().parent.parent / "src" / "topospec" / "graphs" / "schemas"


def node_schema(level: int) -> dict:
    if level == 0:
        kind = {"type": "null"}
        label = {"type": "null"}
        attrs = {"type": "object", "maxProperties": 0}
    else:
        kinds = SPACE_KINDS + (HIERARCHY_KINDS if level == 4 else [])
        kind = {"enum": kinds}
        label = {"type": ["string", "null"]}
        attrs = {"type": "object"} if level == 4 else {"type": "object", "maxProperties": 0}
    return {
        "type": "object",
        "required": ["id", "kind", "area", "centroid", "label", "attrs"],
        "additionalProperties": False,
        "properties": {
            "id": {"type": "string", "minLength": 1},
            "kind": kind,
            "area": {"type": ["number", "null"], "minimum": 0},
            "centroid": {
                "type": ["array", "null"],
                "items": {"type": "number"},
                "minItems": 2,
                "maxItems": 2,
            },
            "label": label,
            "attrs": attrs,
        },
    }


def edge_schema(level: int) -> dict:
    tau = {"enum": EDGE_TAUS} if level >= 2 else {"type": "null"}
    delta = {"enum": EDGE_DELTAS} if level >= 3 else {"type": "null"}
    return {
        "type": "object",
        "required": ["u", "v", "tau", "delta"],
        "additionalProperties": False,
        "properties": {
            "u": {"type": "string"},
            "v": {"type": "string"},
            "tau": tau,
            "delta": delta,
        },
    }


def level_schema(level: int) -> dict:
    containment = (
        {"type": "object", "additionalProperties": {"type": "string"}}
        if level == 4
        else {"type": "object", "maxProperties": 0}
    )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"https://topofield.dev/schemas/spectrum/r{level}.json",
        "title": f"SpectrumGraph level R{level}",
        "type": "object",
        "required": [
            "schema_version",
            "level",
            "building_id",
            "nodes",
            "edges",
            "containment",
            "meta",
        ],
        "additionalProperties": False,
        "properties": {
            "schema_version": {"type": "string"},
            "level": {"const": level},
            "building_id": {"type": "string", "minLength": 1},
            "nodes": {"type": "array", "items": node_schema(level)},
            "edges": {"type": "array", "items": edge_schema(level)},
            "containment": containment,
            "meta": {"type": "object"},
        },
    }


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for k in range(5):
        path = OUT / f"r{k}.json"
        path.write_text(json.dumps(level_schema(k), indent=2) + "\n")
        print(f"wrote {path}")
