"""RED-first tests for a source with syntactically valid JSON but invalid CDL.

Word-count readability must agree with later source word traversal; a falsey
non-list `cdl` cannot silently make a structurally bad source appear readable.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

from oracc_tf import loader


SUB = "riao/ria1"


def _write(data: Path, name: str, doc: dict) -> tuple[Path, bytes]:
    path = data / SUB / "corpusjson" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")
    path.write_bytes(raw)
    return path, raw


@pytest.mark.parametrize("invalid", ["", 0, False, {}, "word", {"node": "l"}])
def test_invalid_root_cdl_is_an_auditable_hazard_not_a_readable_stub(
    tmp_path: Path, invalid: object
) -> None:
    doc = {"textid": "QBAD", "node": "d", "cdl": invalid}
    path, raw = _write(tmp_path, "QBAD.json", doc)
    result = loader.observe_source(path, data=tmp_path)
    assert isinstance(result, loader.SourceHazard)
    assert result.kind == "invalid-cdl"
    assert result.source_id == "QBAD"
    assert result.bytes == len(raw)
    assert result.sha256 == sha256(raw).hexdigest()
    assert result.relative_path == f"{SUB}/corpusjson/QBAD.json"
    with pytest.raises(loader.UnparseableSourceError, match="invalid-cdl"):
        loader.load_edition(path)


@pytest.mark.parametrize("bad_child", [False, 0, "text", [], None])
def test_invalid_nested_cdl_children_are_classified_not_attribute_errors(
    tmp_path: Path, bad_child: object
) -> None:
    path, raw = _write(tmp_path, "QBAD.json", {
        "textid": "QBAD",
        "node": "d",
        "cdl": [
            {"node": "d", "cdl": [{"node": "l", "id": "before"}, bad_child]},
        ],
    })
    obs = loader.observe_source(path, data=tmp_path)
    assert isinstance(obs, loader.SourceHazard)
    assert obs.kind == "invalid-cdl"
    assert obs.sha256 == sha256(raw).hexdigest()


def test_invalid_cdl_is_skipped_with_observable_hazard_and_good_source_kept(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "A.json", {
        "textid": "QA", "node": "d",
        "cdl": [{"node": "l", "id": "a"}, {"node": "d", "cdl": [{"node": "l", "id": "b"}]}],
    })
    _write(tmp_path, "B.json", {"textid": "QB", "node": "d", "cdl": []})
    _write(tmp_path, "C.json", {"textid": "QC", "node": "d", "cdl": ""})
    observed = list(loader.iter_source_observations(tmp_path, subprojects=[SUB]))
    assert len(observed) == 3
    assert [
        x.edition.word_count for x in observed if isinstance(x, loader.ReadableSource)
    ] == [2, 0]
    assert [
        (x.kind, x.source_id) for x in observed if isinstance(x, loader.SourceHazard)
    ] == [("invalid-cdl", "QC")]
    assert [e.text_id for e in loader.iter_editions(
        tmp_path, subprojects=[SUB], skip_unreadable=True
    )] == ["QA", "QB"]
    with pytest.raises(loader.UnparseableSourceError, match="invalid-cdl"):
        list(loader.iter_editions(tmp_path, subprojects=[SUB], skip_unreadable=False))

    survey = loader.survey(tmp_path, subprojects=[SUB])
    assert (survey.source_files, survey.parseable, survey.populated, survey.stubs, survey.unreadable) == (3, 2, 1, 1, 1)
    assert b'"kind":"invalid-cdl"' in loader.canonical_hazard_bytes(survey.hazards)


def test_null_or_absent_cdl_remains_compatible() -> None:
    assert loader.count_words({"node": "d"}) == 0
    assert loader.count_words({"node": "d", "cdl": None}) == 0
    assert loader.count_words({
        "node": "d",
        "cdl": [
            {"node": "l", "id": "one"},
            {"node": "d", "cdl": [{"node": "l", "id": "two"}]},
        ],
    }) == 2
