from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


SCRIPT = Path("scripts/research_issue33_ninmed.py")
WORKFLOW = Path(".github/workflows/issue33-ninmed-research.yml")
ORACC_SHA = "5fa3062632d0971345f5435c6db12adfc379eb67"
REFERENCE_SHA = "9e413c41670117a96272ab2b2727ff9a1f9d3baf"


def load_harness():
    spec = spec_from_file_location("research_issue33_ninmed_hazards", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_reference_tree(tmp_path: Path) -> tuple[Path, Path]:
    reference_dir = tmp_path / "reference"
    tf_dir = tmp_path / "tf"
    reference_dir.mkdir()
    tf_dir.mkdir()
    (reference_dir / "AO -- P000001.json").write_text(
        '{"cdliNumber":"P000001","text":{"allLines":[{"content":[{"type":"Word","cleanValue":"a","uniqueLemma":["A I"]}]}]}}',
        encoding="utf-8",
    )
    (tf_dir / "lemma.tf").write_text("@node\n", encoding="utf-8")
    return reference_dir, tf_dir


def build(module, oracc_dir: Path, reference_dir: Path, tf_dir: Path):
    return module.build_report(
        oracc_dir=oracc_dir,
        reference_dir=reference_dir,
        reference_tf_dir=tf_dir,
        oracc_revision=ORACC_SHA,
        reference_revision=REFERENCE_SHA,
        oracc_licence="This data is released under the CC0 license",
        reference_repository_licence="MIT License",
        reference_source_provenance=(
            "The JSON files have been handed over by personal communication "
            "from Cale Johnson to Dirk Roorda."
        ),
    )


def test_empty_oracc_member_is_auditable_without_filename_identity(tmp_path: Path) -> None:
    module = load_harness()
    oracc_dir = tmp_path / "oracc"
    oracc_dir.mkdir()
    (oracc_dir / "P000001.json").write_text(
        '{"textid":"P000001","cdl":[{"node":"l","f":{"form":"a","cf":"A"}}]}',
        encoding="utf-8",
    )
    # The filename looks like a source identity deliberately. It must never be
    # promoted to one when the source bytes themselves contain no identity.
    (oracc_dir / "P999999.json").write_bytes(b"")
    reference_dir, tf_dir = make_reference_tree(tmp_path)

    report = build(module, oracc_dir, reference_dir, tf_dir)

    assert report["identity"] == {
        "overlap": ("P000001",),
        "oracc_only": (),
        "reference_only": (),
    }
    assert report["source_hazards"] == {
        "oracc": (
            {"relative_path": "P999999.json", "kind": "empty-file", "bytes": 0},
        ),
        "reference": (),
    }
    assert report["oracc_structure"]["documents"] == 1


def test_invalid_json_is_reported_but_duplicate_valid_identity_still_blocks(tmp_path: Path) -> None:
    module = load_harness()
    oracc_dir = tmp_path / "oracc"
    oracc_dir.mkdir()
    (oracc_dir / "valid.json").write_text(
        '{"textid":"P000001","cdl":[]}', encoding="utf-8"
    )
    (oracc_dir / "broken.json").write_text("{not-json", encoding="utf-8")
    reference_dir, tf_dir = make_reference_tree(tmp_path)

    report = build(module, oracc_dir, reference_dir, tf_dir)
    assert report["source_hazards"]["oracc"] == (
        {"relative_path": "broken.json", "kind": "invalid-json", "bytes": 9},
    )

    (oracc_dir / "duplicate.json").write_text(
        '{"textid":"P000001","cdl":[]}', encoding="utf-8"
    )
    with pytest.raises(module.ResearchError, match="duplicate source identity"):
        build(module, oracc_dir, reference_dir, tf_dir)


def test_tree_digest_binds_unreadable_members_too(tmp_path: Path) -> None:
    module = load_harness()
    oracc_dir = tmp_path / "oracc"
    oracc_dir.mkdir()
    (oracc_dir / "valid.json").write_text(
        '{"textid":"P000001","cdl":[]}', encoding="utf-8"
    )
    reference_dir, tf_dir = make_reference_tree(tmp_path)

    before = build(module, oracc_dir, reference_dir, tf_dir)["input_digests"][
        "oracc_json_sha256"
    ]
    (oracc_dir / "empty.json").write_bytes(b"")
    after = build(module, oracc_dir, reference_dir, tf_dir)["input_digests"][
        "oracc_json_sha256"
    ]

    assert before != after


def test_workflow_binds_both_source_trees_to_exact_shas_and_keeps_licence_verbatim() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "repository: alexsosn/ORACC-TF" in text
    assert f"ref: {ORACC_SHA}" in text
    assert "path: .external/oracc-source" in text
    assert "data/asbp/ninmed/corpusjson" in text
    assert "--oracc-dir .external/oracc-source/data/asbp/ninmed/corpusjson" in text
    assert f"ref: {REFERENCE_SHA}" in text
    assert '--reference-repository-licence "MIT License"' in text
    assert "source-data rights not inferred" not in text
