"""#32: RED-first, real ETCSRI word morphology TF vertical slice.

Two pinned ORACC corpusjson witnesses from the checked-in source tree, not
fabricated one-word fixtures. This slice is intentionally not a published
dataset, parsed morpheme ontology, or claim about all 1,456 editions.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from oracc_tf import corpus, loader, metadata, paths, words


PINS = {
    "Q000935": "a2eef2a0337d276191fbda85a4269948fb00f9c3",
    "Q000376": "b2b99268db05b6cbbd1dc4571a5d28592d766a85",
}


def edition_for(textid: str) -> loader.Edition:
    path = paths.DATA / "etcsri" / "corpusjson" / f"{textid}.json"
    assert path.is_file(), "real ETCSRI corpusjson witness required"
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["project"] == "etcsri"
    assert doc["textid"] == textid
    return loader.Edition(
        subproject="etcsri",
        text_id=textid,
        path=path,
        doc=doc,
        word_count=loader.count_words(doc),
    )


def tf_for(tmp_path: Path, *editions: loader.Edition):
    report = corpus.build_tf(
        tmp_path,
        editions=editions,
        metadata_index=metadata.MetadataIndex.empty(),
        dataset_title="ORACC-TF ETCSRI (research vertical slice)",
    )
    return report, corpus.load_tf(tmp_path)


def canonical(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def test_two_real_etcsri_editions_round_trip_native_morphology_and_para(tmp_path: Path) -> None:
    samples = (edition_for("Q000935"), edition_for("Q000376"))
    assert [e.word_count for e in samples] == [7, 286]

    report, api = tf_for(tmp_path, *samples)
    assert report.documents == 2
    assert report.words == 293
    assert report.sign_word_membership_errors == 0
    assert report.word_line_membership_errors == 0
    assert report.section_path_errors == 0

    by_doc_word = {
        (api.F.document_key.v(node), api.F.source_id.v(node)): node
        for node in api.F.otype.s("word")
    }
    seen_para = 0
    for edition in samples:
        for original in words.source_words(edition.doc):
            word = by_doc_word[(edition.key, original["id"])]
            f = original.get("f") or {}
            for feature in ("base", "morph", "morph2"):
                assert getattr(api.F, feature).v(word) == f.get(feature), (
                    edition.key, original["id"], feature
                )
            source_morph = {
                name: f[name] for name in ("base", "morph", "morph2") if name in f
            }
            assert api.F.morphology_json.v(word) == (
                canonical(source_morph) if source_morph else None
            )
            for source_key, feature in (("para", "para_json"), ("props", "props_json")):
                expected = canonical(original[source_key]) if source_key in original else None
                assert getattr(api.F, feature).v(word) == expected, (
                    edition.key, original["id"], feature
                )
            if original.get("para"):
                seen_para += 1
            assert api.F.gdl_json.v(word) == (
                canonical(f["gdl"]) if "gdl" in f else None
            )
    assert seen_para == 52
    assert "phrase" in {api.F.chunk_type.v(node) for node in api.F.otype.s("chunk")}
    assert api.F.morph.v(by_doc_word[("etcsri:Q000935", "Q000935.l04855")]) == "N1=Urnammak"
    assert api.F.morph2.v(by_doc_word[("etcsri:Q000935", "Q000935.l04855")]) == "N1=NAME"
    assert api.F.base.v(by_doc_word[("etcsri:Q000935", "Q000935.l04855")]) == "ur-{d}namma"
    assert "ORACC-TF ETCSRI" in (tmp_path / "otext.tf").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "f_update,word_update,reason",
    [
        ({"morph": ["N1=stem"]}, {}, "morph"),
        ({"morph2": {"N1": "STEM"}}, {}, "morph2"),
        ({"base": False}, {}, "base"),
        ({}, {"para": {"type": "sentence"}}, "para"),
        ({}, {"props": "discourse"}, "props"),
    ],
)
def test_malformed_etcsri_source_annotations_fail_closed(
    tmp_path: Path,
    f_update: dict,
    word_update: dict,
    reason: str,
) -> None:
    original = edition_for("Q000935")
    node = next(words.source_words(original.doc))
    node["f"].update(f_update)
    node.update(word_update)
    with pytest.raises((ValueError, corpus.CorpusBuildError), match=reason):
        tf_for(tmp_path, original)


def test_etcsri_word_features_are_not_added_to_royal_datasets(tmp_path: Path) -> None:
    """No silent schema/content change for the already published 1.0 dataset."""
    edition = edition_for("Q000935")
    royal_test = loader.Edition(
        subproject="test/royal",
        text_id=edition.text_id,
        path=edition.path,
        doc=edition.doc,
        word_count=edition.word_count,
    )
    corpus.build_tf(
        tmp_path,
        editions=(royal_test,),
        metadata_index=metadata.MetadataIndex.empty(),
    )
    for name in ("base", "morph", "morph2", "morphology_json", "para_json", "props_json"):
        assert not (tmp_path / f"{name}.tf").exists()


def test_explicit_null_morphology_is_not_conflated_with_absence(tmp_path: Path) -> None:
    edition = edition_for("Q000935")
    first = next(words.source_words(edition.doc))
    first["f"]["morph"] = None
    first["f"].pop("base", None)
    report, api = tf_for(tmp_path, edition)
    by_source = {
        api.F.source_id.v(node): node for node in api.F.otype.s("word")
    }
    node = by_source[first["id"]]
    assert api.F.morph.v(node) is None
    payload = json.loads(api.F.morphology_json.v(node))
    assert "morph" in payload and payload["morph"] is None
    assert "base" not in payload
