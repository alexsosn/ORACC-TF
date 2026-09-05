"""Issue #58 RED-first whole-corpus acceptance tests for OBABAT TF."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from oracc_tf import corpus, obabat, publishing


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OVERLAP = ROOT / "docs" / "research" / "issue-39-obabat-overlap.json"


def _feature_values(api, name: str, otype: str):
    feature = api.Fs(name)
    assert feature is not None, name
    return [feature.v(node) for node in api.F.otype.s(otype)]


@pytest.mark.corpus
def test_obabat_full_build_preserves_counts_overlap_and_zero_unicode(tmp_path):
    out = tmp_path / "obabat"
    report = obabat.build_tf(out, data=DATA, overlap_path=OVERLAP)

    assert report.documents == 121
    assert report.populated_documents == 121
    assert report.stub_documents == 0
    assert report.unique_document_keys == 121
    assert report.document_key_collisions == 0
    assert report.words == 9517
    assert report.signs == 27208
    assert report.unicode_signs == 0
    assert report.lines == 3242
    assert report.sign_word_membership_errors == 0
    assert report.word_line_membership_errors == 0

    api = corpus.load_tf(out)
    document_keys = _feature_values(api, "document_key", "document")
    assert len(document_keys) == 121
    assert len(set(document_keys)) == 121
    assert all(key.startswith("obabat/atletters:P") for key in document_keys)

    statuses = _feature_values(api, "nino_overlap_status", "document")
    assert statuses.count("exact-p-number-overlap") == 86
    assert statuses.count("not-in-pinned-nino-unverified") == 35
    assert all(status != "clean" for status in statuses)

    assert all(value is None for value in _feature_values(api, "utf8", "sign"))
    assert all(value is None for value in _feature_values(api, "readingu", "sign"))

    cf_values = _feature_values(api, "cf", "word")
    assert len(cf_values) == 9517
    assert sum(value is not None for value in cf_values) == 8941

    discourse = _feature_values(api, "discourse", "word")
    assert sum(value is not None for value in discourse) == 9516
    props = _feature_values(api, "props_json", "word")
    assert sum(value is not None for value in props) >= 9516

    sidecar = json.loads((out / obabat.OVERLAP_SIDECAR).read_text(encoding="utf-8"))
    assert sidecar["source_dataset"] == "obabat/atletters"
    assert sidecar["source_blob"] == "f3dae9f3e713683ebc4c49075ff8475a44e3b1f8"
    assert len(sidecar["overlap_ids"]) == 86
    assert len(sidecar["not_in_pinned_nino_ids"]) == 35
    assert "clean" not in json.dumps(sidecar).lower()


@pytest.mark.corpus
def test_p510527_tf_round_trip_keeps_source_lexical_analysis(tmp_path):
    out = tmp_path / "obabat"
    obabat.build_tf(out, data=DATA, overlap_path=OVERLAP)
    api = corpus.load_tf(out)

    source_id = api.Fs("source_id")
    cf = api.Fs("cf")
    pos = api.Fs("pos")
    epos = api.Fs("epos")
    document_key = api.Fs("document_key")
    gdl_json = api.Fs("gdl_json")
    props_json = api.Fs("props_json")

    matches = {}
    for node in api.F.otype.s("word"):
        if document_key.v(node) != "obabat/atletters:P510527":
            continue
        value = cf.v(node)
        if value in {"ana", "Ilšu-ibni", "Šamaš"} and value not in matches:
            matches[value] = node

    assert set(matches) == {"ana", "Ilšu-ibni", "Šamaš"}
    assert (pos.v(matches["ana"]), epos.v(matches["ana"])) == ("PRP", "PRP")
    assert pos.v(matches["Ilšu-ibni"]) == "PN"
    assert pos.v(matches["Šamaš"]) == "DN"
    assert gdl_json.v(matches["ana"])
    assert props_json.v(matches["ana"])
    assert source_id.v(matches["ana"])


@pytest.mark.corpus
def test_obabat_rebuild_is_deterministic_and_publication_is_registered(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    obabat.build_tf(first, data=DATA, overlap_path=OVERLAP)
    obabat.build_tf(second, data=DATA, overlap_path=OVERLAP)

    first_files = {path.name: path.read_bytes() for path in first.iterdir() if path.is_file()}
    second_files = {path.name: path.read_bytes() for path in second.iterdir() if path.is_file()}
    assert first_files == second_files

    root, report = publishing.build_registered_tf(
        tmp_path / "published", "obabat-atletters", data=DATA
    )
    assert root == tmp_path / "published" / "obabat-atletters" / "tf" / obabat.TF_VERSION
    assert report.documents == 121
    assert (root / "otype.tf").is_file()
    assert (root / obabat.OVERLAP_SIDECAR).is_file()
