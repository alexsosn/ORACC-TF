from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


SCRIPT = Path("scripts/research_issue33_ninmed.py")


def load_harness():
    spec = spec_from_file_location("research_issue33_ninmed_report", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_source_native_structure_censuses_keep_incompatible_units_separate() -> None:
    module = load_harness()
    oracc = {
        "textid": "P000001",
        "cdl": [
            {"node": "d", "type": "line-start", "label": "1"},
            {"node": "l", "f": {"form": "a", "gdl": [{"v": "a"}]}},
            {"node": "l", "f": {"form": "b", "gdl": []}},
            {"node": "l", "f": {"form": "c"}},
        ],
    }
    reference = {
        "cdliNumber": "P000001",
        "text": {
            "allLines": [
                {
                    "prefix": "1.",
                    "content": [
                        {"type": "Word", "cleanValue": "a", "parts": [{"type": "ValueToken"}]},
                        {"type": "Joiner", "cleanValue": "."},
                        {"type": "Word", "cleanValue": "b", "parts": []},
                    ],
                },
                {"prefix": "2.", "content": []},
            ]
        },
    }

    assert module.oracc_structure_census([oracc]) == {
        "documents": 1,
        "line_starts": 1,
        "words": 3,
        "gdl_top_level_entries": 1,
        "words_with_empty_gdl": 1,
        "words_without_gdl": 1,
    }
    assert module.reference_structure_census([reference]) == {
        "documents": 1,
        "lines": 2,
        "words": 2,
        "word_parts": 1,
        "words_with_empty_parts": 1,
        "empty_lines": 1,
    }


def test_paired_transliteration_witness_is_exact_and_does_not_normalize() -> None:
    module = load_harness()
    oracc = {
        "textid": "P000001",
        "cdl": [
            {"node": "l", "f": {"form": "DU₃.DU₃.BI"}},
            {"node": "l", "f": {"form": "ina"}},
        ],
    }
    reference = {
        "cdliNumber": "P000001",
        "text": {
            "allLines": [
                {
                    "content": [
                        {"type": "Word", "cleanValue": "DU3.DU3.BI"},
                        {"type": "Word", "cleanValue": "ina"},
                    ]
                }
            ]
        },
    }

    witness = module.paired_transliteration_witness(oracc, reference)
    assert witness == {
        "text_id": "P000001",
        "oracc_words": ("DU₃.DU₃.BI", "ina"),
        "reference_words": ("DU3.DU3.BI", "ina"),
        "same_word_count": True,
        "exact_sequence_equal": False,
        "first_difference": 0,
    }


def test_build_report_records_pins_digests_and_independent_feature_models(tmp_path: Path) -> None:
    module = load_harness()
    oracc_dir = tmp_path / "oracc"
    reference_dir = tmp_path / "reference"
    tf_dir = tmp_path / "tf"
    oracc_dir.mkdir()
    reference_dir.mkdir()
    tf_dir.mkdir()

    (oracc_dir / "P000001.json").write_text(
        '{"textid":"P000001","cdl":[{"node":"l","f":{"form":"a","cf":"A","pos":"N"}}]}',
        encoding="utf-8",
    )
    (reference_dir / "AO -- P000001.json").write_text(
        '{"cdliNumber":"P000001","text":{"allLines":[{"content":[{"type":"Word","cleanValue":"a","uniqueLemma":["A I"]}]}]}}',
        encoding="utf-8",
    )
    (tf_dir / "lemma.tf").write_text("@node\n", encoding="utf-8")
    (tf_dir / "reading.tf").write_text("@node\n", encoding="utf-8")

    report = module.build_report(
        oracc_dir=oracc_dir,
        reference_dir=reference_dir,
        reference_tf_dir=tf_dir,
        oracc_revision="oracc-pin",
        reference_revision="reference-pin",
        oracc_licence="CC0 verbatim",
        reference_repository_licence="MIT verbatim",
        reference_source_provenance="personal-communication provenance verbatim",
    )

    assert report["schema_version"] == 1
    assert report["pins"] == {
        "oracc_revision": "oracc-pin",
        "reference_revision": "reference-pin",
    }
    assert report["licences"] == {
        "oracc": "CC0 verbatim",
        "reference_repository": "MIT verbatim",
    }
    assert report["reference_source_provenance"] == "personal-communication provenance verbatim"
    assert report["identity"]["overlap"] == ("P000001",)
    assert report["oracc_lexical"]["field_nonempty"]["cf"] == 1
    assert report["oracc_lexical"]["field_nonempty"]["pos"] == 1
    assert report["reference_lexical"]["unique_lemma_assignments"] == 1
    assert report["reference_tf_features"] == ("lemma", "reading")
    assert report["paired_witnesses"][0]["exact_sequence_equal"] is True
    assert len(report["input_digests"]["oracc_json_sha256"]) == 64
    assert len(report["input_digests"]["reference_json_sha256"]) == 64
