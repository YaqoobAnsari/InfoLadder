"""Generate the versioned JSON Schema files for tiers T0..T5 (schema v2, D-014).

Regenerate after any schema change:
    $TOPOSPEC_PYTHON scripts/gen_schemas.py
Generated files are committed toolkit artifacts, loaded by
topospec.graphs.validate.json_schema_for_level.
"""

import json
from pathlib import Path

SPACE_KINDS = ["room", "door", "corridor", "transition"]
T1_KINDS = ["room", "corridor", "transition"]  # doors appear at T2
HIERARCHY_KINDS = ["corridor-cluster", "zone", "wing"]
EDGE_DELTAS = ["both", "forward", "backward"]
MEASURE_ATTR_KEYS = ["area_px", "eq_radius", "inradius", "n_subnodes", "n_doors"]

OUT = Path(__file__).resolve().parent.parent / "src" / "topospec" / "graphs" / "schemas"


def node_schema(level: int) -> dict:
    if level == 0:
        kind = {"type": "null"}
        label = {"type": "null"}
    elif level == 1:
        kind = {"enum": T1_KINDS}
        label = {"type": ["string", "null"]}
    elif level < 5:
        kind = {"enum": SPACE_KINDS}
        label = {"type": ["string", "null"]}
    else:
        kind = {"enum": SPACE_KINDS + HIERARCHY_KINDS}
        label = {"type": ["string", "null"]}

    if level < 3:
        area = {"type": "null"}
        attrs = {"type": "object", "maxProperties": 0}
    else:
        area = {"type": ["number", "null"], "minimum": 0}
        # space nodes: measure keys only; hierarchy nodes (T5) carry free-form
        # blocks — enforced semantically in validate.py, structurally loose here
        attrs = {"type": "object"}

    return {
        "type": "object",
        "required": ["id", "kind", "area", "centroid", "label", "attrs"],
        "additionalProperties": False,
        "properties": {
            "id": {"type": "string", "minLength": 1},
            "kind": kind,
            "area": area,
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
    delta = {"enum": EDGE_DELTAS} if level >= 4 else {"type": "null"}
    return {
        "type": "object",
        "required": ["u", "v", "delta"],
        "additionalProperties": False,
        "properties": {
            "u": {"type": "string"},
            "v": {"type": "string"},
            "delta": delta,
        },
    }


def level_schema(level: int) -> dict:
    containment = (
        {"type": "object", "additionalProperties": {"type": "string"}}
        if level == 5
        else {"type": "object", "maxProperties": 0}
    )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"https://topofield.dev/schemas/spectrum/t{level}.json",
        "title": f"SpectrumGraph tier T{level}",
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
    for old in OUT.glob("r*.json"):
        old.unlink()  # schema v1 artifacts superseded (D-014)
    for k in range(6):
        path = OUT / f"t{k}.json"
        path.write_text(json.dumps(level_schema(k), indent=2) + "\n")
        print(f"wrote {path}")
