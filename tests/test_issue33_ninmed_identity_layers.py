from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path

import pytest


SCRIPT = Path("scripts/research_issue33_ninmed.py")
WORKFLOW = Path(".github/workflows/issue33-ninmed-research.yml")


def load_harness():
    spec = spec_from_file_location("research_issue33_ninmed_identity_layers", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_oracc_catalogue_uses_member_and_embedded_identity(tmp_path: Path) -> None:
    module = load_harness()
    catalogue = tmp_path / "catalogue.json"
    catalogue.write_text(
        json.dumps(
            {
                "type": "catalogue",
                "project": "asbp/ninmed",
                "members": {
                    "P000001": {
                        "id_text": "P000001",
                        "designation": "Tablet A",
                        "museum_number": "BM 1",
                    },
                    "P000002": {
                        "id_text": "P000002",
                        "designation": "Tablet B",
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    census = module.oracc_catalogue_census(catalogue)
    assert census == {
        "project": "asbp/ninmed",
        "member_count": 2,
        "member_ids": ("P000001", "P000002"),
        "metadata_nonempty": {"designation": 2, "museum_number": 1},
    }


def test_oracc_catalogue_rejects_key_id_text_disagreement(tmp_path: Path) -> None:
    module = load_harness()
    catalogue = tmp_path / "catalogue.json"
    catalogue.write_text(
        '{"type":"catalogue","project":"asbp/ninmed","members":{"P000001":{"id_text":"P999999"}}}',
        encoding="utf-8",
    )

    with pytest.raises(module.ResearchError, match="catalogue member identity"):
        module.oracc_catalogue_census(catalogue)


def test_reference_tf_document_ids_parse_actual_pnumber_feature_contract(tmp_path: Path) -> None:
    module = load_harness()
    tf_dir = tmp_path / "tf"
    tf_dir.mkdir()
    (tf_dir / "pnumber.tf").write_text(
        "@node\n@description=P number of a document\n@valueType=str\n\n59226\tP000001\nP000003\nP000004\n",
        encoding="utf-8",
    )

    assert module.reference_tf_document_ids(tf_dir) == (
        "P000001",
        "P000003",
        "P000004",
    )


def test_report_keeps_four_identity_layers_separate(tmp_path: Path) -> None:
    module = load_harness()
    oracc_dir = tmp_path / "oracc"
    reference_dir = tmp_path / "reference"
    tf_dir = tmp_path / "tf"
    oracc_dir.mkdir()
    reference_dir.mkdir()
    tf_dir.mkdir()
    catalogue = tmp_path / "catalogue.json"

    (oracc_dir / "opaque-a.json").write_text(
        '{"textid":"P000001","cdl":[{"node":"l","f":{"form":"a","cf":"A"}}]}',
        encoding="utf-8",
    )
    # The empty member deliberately looks like an identity in its filename. The
    # hazard itself still must not acquire a text_id from that filename.
    (oracc_dir / "P000002.json").write_bytes(b"")
    catalogue.write_text(
        '{"type":"catalogue","project":"asbp/ninmed","members":{'
        '"P000001":{"id_text":"P000001","designation":"A"},'
        '"P000002":{"id_text":"P000002","designation":"B"},'
        '"P000005":{"id_text":"P000005","designation":"catalogue only"}'
        '}}',
        encoding="utf-8",
    )
    (reference_dir / "old-a.json").write_text(
        '{"cdliNumber":"P000001","text":{"allLines":[{"content":[{"type":"Word","cleanValue":"a","uniqueLemma":["A I"]}]}]}}',
        encoding="utf-8",
    )
    (reference_dir / "old-b.json").write_text(
        '{"cdliNumber":"P000002","text":{"allLines":[]}}', encoding="utf-8"
    )
    (reference_dir / "old-c.json").write_text(
        '{"cdliNumber":"P000003","text":{"allLines":[]}}', encoding="utf-8"
    )
    (tf_dir / "pnumber.tf").write_text(
        "@node\n@valueType=str\n\n100\tP000001\nP000002\nP000004\n",
        encoding="utf-8",
    )
    (tf_dir / "lemma.tf").write_text("@node\n@valueType=str\n", encoding="utf-8")

    report = module.build_report(
        oracc_dir=oracc_dir,
        oracc_catalogue=catalogue,
        reference_dir=reference_dir,
        reference_tf_dir=tf_dir,
        oracc_revision="oracc-pin",
        reference_revision="reference-pin",
        oracc_licence="CC0 verbatim",
        reference_repository_licence="MIT verbatim",
        reference_source_provenance="source provenance",
    )

    assert report["oracc_catalogue"]["member_ids"] == (
        "P000001",
        "P000002",
        "P000005",
    )
    assert report["identity_layers"] == {
        "oracc_body_vs_catalogue": {
            "overlap": ("P000001",),
            "oracc_body_only": (),
            "catalogue_only": ("P000002", "P000005"),
        },
        "reference_json_vs_catalogue": {
            "overlap": ("P000001", "P000002"),
            "reference_json_only": ("P000003",),
            "catalogue_only": ("P000005",),
        },
        "reference_tf_vs_oracc_body": {
            "overlap": ("P000001",),
            "reference_tf_only": ("P000002", "P000004"),
            "oracc_body_only": (),
        },
        "reference_tf_vs_reference_json": {
            "overlap": ("P000001", "P000002"),
            "reference_tf_only": ("P000004",),
            "reference_json_only": ("P000003",),
        },
    }
    assert report["source_hazards"]["oracc"] == (
        {"relative_path": "P000002.json", "kind": "empty-file", "bytes": 0},
    )
    assert "text_id" not in report["source_hazards"]["oracc"][0]
    assert len(report["input_digests"]["oracc_catalogue_sha256"]) == 64


def test_workflow_pins_catalogue_from_same_oracc_revision() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "data/asbp/ninmed/catalogue.json" in text
    assert "--oracc-catalogue .external/oracc-source/data/asbp/ninmed/catalogue.json" in text
