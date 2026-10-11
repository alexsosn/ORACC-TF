from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path

import pytest


SCRIPT = Path("scripts/research_issue33_ninmed.py")


def load_harness():
    assert SCRIPT.is_file(), "ISSUE-33 research harness has not been implemented yet"
    spec = spec_from_file_location("research_issue33_ninmed", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_identity_overlap_uses_source_ids_not_filenames_or_museum_labels(tmp_path: Path) -> None:
    module = load_harness()
    oracc = tmp_path / "oracc"
    reference = tmp_path / "reference"

    _write_json(oracc / "P000001.json", {"textid": "P000001", "cdl": []})
    _write_json(reference / "AO.1 -- P000001.json", {"number": "AO.1", "cdliNumber": "P000001"})
    _write_json(reference / "K.2 -- P000002.json", {"number": "K.2", "cdliNumber": "P000002"})

    assert module.oracc_document_ids(oracc) == ("P000001",)
    assert module.reference_document_ids(reference) == ("P000001", "P000002")
    assert module.identity_overlap(("P000001",), ("P000001", "P000002")) == {
        "overlap": ("P000001",),
        "oracc_only": (),
        "reference_only": ("P000002",),
    }


def test_duplicate_source_identity_fails_closed(tmp_path: Path) -> None:
    module = load_harness()
    reference = tmp_path / "reference"
    _write_json(reference / "AO.1 -- P000001.json", {"cdliNumber": "P000001"})
    _write_json(reference / "K.2 -- P000001.json", {"cdliNumber": "P000001"})

    with pytest.raises(module.ResearchError, match="duplicate"):
        module.reference_document_ids(reference)


def test_oracc_lexical_census_counts_only_nonempty_source_fields() -> None:
    module = load_harness()
    document = {
        "cdl": [
            {
                "node": "c",
                "cdl": [
                    {
                        "node": "l",
                        "f": {
                            "cf": "epēšu",
                            "gw": "do",
                            "pos": "V",
                            "epos": "V/i",
                            "sense": "perform",
                            "norm": "ēpuš",
                            "inst": "instance",
                        },
                    },
                    {"node": "l", "f": {"pos": "u", "cf": "", "gw": None}},
                ],
            }
        ]
    }

    census = module.oracc_lexical_census([document])
    assert census["words"] == 2
    assert census["field_nonempty"] == {
        "cf": 1,
        "gw": 1,
        "pos": 2,
        "epos": 1,
        "sense": 1,
        "norm": 1,
        "inst": 1,
    }


def test_reference_lexical_census_preserves_unique_lemma_multiplicity() -> None:
    module = load_harness()
    document = {
        "text": {
            "allLines": [
                {
                    "content": [
                        {"type": "Word", "value": "A", "uniqueLemma": ["lemma I", "suffix I"]},
                        {"type": "Word", "value": "B", "uniqueLemma": []},
                        {"type": "Joiner", "value": "."},
                    ]
                }
            ]
        }
    }

    census = module.reference_lexical_census([document])
    assert census == {
        "words": 2,
        "words_with_unique_lemma": 1,
        "unique_lemma_assignments": 2,
        "max_unique_lemmas_per_word": 2,
    }


def test_tf_feature_inventory_is_filename_based_and_sorted(tmp_path: Path) -> None:
    module = load_harness()
    tf_dir = tmp_path / "tf"
    tf_dir.mkdir()
    for name in ("lemma.tf", "otype.tf", "pos.tf", "oslots.tf", "zeta.tf"):
        (tf_dir / name).write_text("@node\n", encoding="utf-8")
    (tf_dir / "README.md").write_text("not a feature", encoding="utf-8")

    assert module.tf_feature_names(tf_dir) == ("lemma", "oslots", "otype", "pos", "zeta")


def test_report_serialization_is_canonical_and_order_independent() -> None:
    module = load_harness()
    left = {"z": [2, 1], "a": {"y": 2, "x": 1}}
    right = {"a": {"x": 1, "y": 2}, "z": [2, 1]}

    assert module.canonical_report_bytes(left) == module.canonical_report_bytes(right)
    assert module.canonical_report_bytes(left).endswith(b"\n")
