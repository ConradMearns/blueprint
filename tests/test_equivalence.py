"""Every representation of the ecommerce schema must draw the same diagram.

`fixtures/ecommerce.canvas.json` is the known-good fingerprint of the
attribute-based reference schema (`examples/ecommerce.linkml.yaml`): tables and
columns, foreign-key edges, and problems -- everything the diagram paints,
minus positions. See `fixtures/README.md`.
"""

import json
from pathlib import Path

import pytest

from blueprint.parse import Schema, parse_linkml_file

ROOT = Path(__file__).parent.parent
FIXTURES = Path(__file__).parent / "fixtures"


def _sorted(fp: dict) -> dict:
    """Order-independent form of a fingerprint, so declaration order doesn't matter."""
    return {
        "tables": sorted(
            ({**t, "columns": sorted(t["columns"], key=lambda c: c["name"])} for t in fp["tables"]),
            key=lambda t: t["name"],
        ),
        "edges": sorted(fp["edges"], key=lambda e: (e["fromClass"], e["fromSlot"])),
        "problems": sorted(fp["problems"], key=lambda p: (p["className"], p["slot"])),
    }


def fingerprint(schema: Schema) -> dict:
    return _sorted(
        {
            "tables": [
                {
                    "name": c.name,
                    "columns": [
                        {
                            "name": s.name,
                            "type": s.range,
                            "pk": s.pk,
                            "fk": s.ref_class is not None,
                            "required": s.required,
                            "multivalued": s.multivalued,
                            "unresolved": s.unresolved,
                        }
                        for s in c.slots
                    ],
                }
                for c in schema.classes
            ],
            "edges": [
                {
                    "fromClass": fk.from_class,
                    "fromSlot": fk.from_slot,
                    "toClass": fk.to_class,
                    "toSlot": fk.to_slot,
                    "required": fk.required,
                    "multivalued": fk.multivalued,
                }
                for fk in schema.foreign_keys
            ],
            "problems": [
                {"level": p.level, "className": p.class_name, "slot": p.slot, "message": p.message}
                for p in schema.problems
            ],
        }
    )


KNOWN_GOOD = _sorted(json.loads((FIXTURES / "ecommerce.canvas.json").read_text()))


def test_baseline_matches_known_good():
    assert fingerprint(parse_linkml_file(ROOT / "examples" / "ecommerce.linkml.yaml")) == KNOWN_GOOD


@pytest.mark.parametrize(
    "file",
    ["ecommerce.slots.yaml", "ecommerce.attributes-import.yaml", "ecommerce.slots-import.yaml"],
)
def test_variant_draws_same_diagram(file):
    assert fingerprint(parse_linkml_file(FIXTURES / file)) == KNOWN_GOOD
