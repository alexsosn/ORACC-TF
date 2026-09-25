"""Pinned real-source acceptance gate for the M9 translation graph."""

from __future__ import annotations

import os
import json
from pathlib import Path

import pytest

from oracc_tf import corpus, translations
from oracc_tf import paths


@pytest.mark.corpus
def test_pinned_riao_tei_archive_builds_source_aligned_translation_graph(tmp_path: Path):
    archive = os.environ.get("ORACC_TF_M9_TEI_ARCHIVE")
    if not archive:
        pytest.skip("set ORACC_TF_M9_TEI_ARCHIVE to run the pinned real-source gate")

    index = translations.parse_tei_archive(archive)
    records = tuple(index.records.values())
    source_units = sum(len(record.units) for record in records)
    assert len(records) == 1_639
    assert source_units == 9_301
    assert sum(
        not unit.sref or not unit.eref
        for record in records
        for unit in record.units
    ) == 668

    report = corpus.build_full_tf(
        tmp_path / "tf",
        data=Path(os.environ.get("ORACC_TF_DATA", paths.DATA)),
        translations_by_document=index.as_document_map(),
    )
    assert report.translation_units == 6_792
    assert report.translation_gaps == 2_509
    assert report.translation_units + report.translation_gaps == source_units
    assert any("unresolved source line range" in gap for gap in report.translation_gap_details)
    assert any("document absent from corpus build" in gap for gap in report.translation_gap_details)

    gap_inventory = json.loads(
        (tmp_path / "tf" / corpus.TRANSLATION_GAP_FILENAME).read_text(encoding="utf-8")
    )
    assert gap_inventory["schema"] == corpus.TRANSLATION_GAP_SCHEMA
    assert gap_inventory["count"] == report.translation_gaps == 2_509
    assert sum(gap_inventory["category_counts"].values()) == 2_509
    assert gap_inventory["category_counts"] == {
        "document-not-in-corpus": 4,
        "missing-source-range": 668,
        "unresolved-source-range": 1_837,
    }
    assert len(gap_inventory["gaps"]) == 2_509
    assert sum(
        gap["translation_source_id"] is None for gap in gap_inventory["gaps"]
    ) == 2_452
    assert {
        gap["source_sha256"] for gap in gap_inventory["gaps"]
    } == {index.records["riao-teiCorpus-20241202.zip"].source_sha256}

    api = corpus.load_tf(tmp_path / "tf")
    units_by_id = {
        api.F.translation_id.v(node): node
        for node in api.F.otype.s("translation_unit")
    }
    long_unit = units_by_id["riao/ria2:Q009244:Q009244_project-en.0"]
    assert api.F.translation_rows.v(long_unit) == 72
    assert api.F.translation_text.v(long_unit) == "(Not yet translated.)"
    assert api.F.translation_eref.v(long_unit) == "Q009244.72"
    assert any(
        api.F.translation_sref.v(node) == api.F.translation_eref.v(node)
        for node in api.F.otype.s("translation_unit")
    )

    # This published range is inclusive and remains attached to exactly the
    # source lines' current TF slots, including any explicit synthetic anchors.
    sample_record = index.get("riao/ria1:Q001801")
    assert sample_record is not None
    source_unit = sample_record.units[0]
    sample = units_by_id[f"riao/ria1:Q001801:{source_unit.source_id}"]
    expected_slots: set[int] = set()
    for source_ref in (f"Q001801.{line}" for line in range(1, 16)):
        line_nodes = [
            node
            for node in api.F.line.s(source_ref)
            if api.F.document_key.v(node) == "riao/ria1:Q001801"
        ]
        assert len(line_nodes) == 1
        expected_slots.update(api.L.d(line_nodes[0], otype="sign"))
    assert tuple(api.L.d(sample, otype="sign")) == tuple(sorted(expected_slots))
    assert api.F.translation_sref.v(sample) == "Q001801.1"
    assert api.F.translation_eref.v(sample) == "Q001801.15"
    assert any("subtype=dollar:" in gap for gap in report.translation_gap_details)
