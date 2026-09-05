"""Issue #58 RED-first unit/source fixtures for the OBABAT adapter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from oracc_tf import loader, obabat, words


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OVERLAP = ROOT / "docs" / "research" / "issue-39-obabat-overlap.json"
P510527 = DATA / "obabat" / "atletters" / "corpusjson" / "P510527.json"


def test_obabat_identity_and_overlap_provenance_are_exact():
    provenance = obabat.load_overlap_provenance(DATA, OVERLAP)

    assert obabat.SOURCE_DATASET == "obabat/atletters"
    assert obabat.PUBLICATION_SLUG == "obabat-atletters"
    assert provenance.source_blob == "f3dae9f3e713683ebc4c49075ff8475a44e3b1f8"
    assert provenance.nino_revision == "cd8ffe826a598af4715fd724387d9834ec1300d8"
    assert provenance.nino_blob == "9d9d07d0f5f80f03aadae43e87bedddcc2d05ad1"
    assert len(provenance.overlap_ids) == 86
    assert len(provenance.unmatched_ids) == 35
    assert provenance.overlap_ids.isdisjoint(provenance.unmatched_ids)
    assert len(provenance.overlap_ids | provenance.unmatched_ids) == 121
    assert provenance.status("P510527") == "exact-p-number-overlap"
    assert provenance.status("P511156") == "not-in-pinned-nino-unverified"


def test_overlap_provenance_fails_closed_on_partition_drift(tmp_path):
    manifest = json.loads(OVERLAP.read_text(encoding="utf-8"))
    manifest["not_in_pinned_nino_ids"] = manifest["not_in_pinned_nino_ids"][:-1]
    changed = tmp_path / "overlap.json"
    changed.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(obabat.OBABATProvenanceError, match="partition|121|member"):
        obabat.load_overlap_provenance(DATA, changed)


def test_overlap_provenance_fails_closed_on_source_blob_drift(tmp_path):
    fake_data = tmp_path / "data"
    source_dir = fake_data / "obabat" / "atletters"
    source_dir.mkdir(parents=True)
    original = (DATA / "obabat" / "atletters" / "corpus.json").read_bytes()
    (source_dir / "corpus.json").write_bytes(original + b"\n")

    with pytest.raises(obabat.OBABATProvenanceError, match="blob"):
        obabat.load_overlap_provenance(fake_data, OVERLAP)


def test_overlap_provenance_missing_or_malformed_fails_closed(tmp_path):
    with pytest.raises(obabat.OBABATProvenanceError):
        obabat.load_overlap_provenance(DATA, tmp_path / "missing.json")

    malformed = tmp_path / "malformed.json"
    malformed.write_text("{}", encoding="utf-8")
    with pytest.raises(obabat.OBABATProvenanceError):
        obabat.load_overlap_provenance(DATA, malformed)


def test_p510527_lexical_and_source_properties_are_projected_without_fabrication():
    edition = loader.load_edition(P510527)
    assert edition.key == "obabat/atletters:P510527"
    by_cf = {
        word.cf: word
        for word in words.iter_words(edition.doc)
        if word.cf in {"ana", "Ilšu-ibni", "Šamaš"}
    }
    assert set(by_cf) == {"ana", "Ilšu-ibni", "Šamaš"}

    ana = by_cf["ana"]
    ilsu = by_cf["Ilšu-ibni"]
    shamash = by_cf["Šamaš"]
    assert (ana.cf, ana.pos, ana.epos) == ("ana", "PRP", "PRP")
    assert ilsu.pos == "PN"
    assert shamash.pos == "DN"

    extra = obabat.project_word_features(ana)
    assert extra["props_json"] == json.dumps(
        ana.source["props"], ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    assert extra["discourse"] == "D"
    assert extra.get("base") is None
    assert extra.get("morph") is None
    assert extra.get("morph2") is None
    assert all(sign.value.get("utf8") in (None, "") for sign in ana.signs)


def test_unlemmatised_obabat_word_is_retained_by_existing_word_layer():
    corpus_dir = DATA / "obabat" / "atletters" / "corpusjson"
    witness = None
    for path in sorted(corpus_dir.glob("P*.json")):
        edition = loader.load_edition(path)
        witness = next((word for word in words.iter_words(edition.doc) if word.cf is None), None)
        if witness is not None:
            break

    assert witness is not None
    assert witness.source_id
    assert witness.lemmaknown == 0
    projected = obabat.project_word_features(witness)
    assert "props_json" in projected or "discourse" in projected
