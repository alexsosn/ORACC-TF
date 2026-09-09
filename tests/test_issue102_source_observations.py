from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

from oracc_tf import corpus, loader, metadata


EMPTY_SHA256 = sha256(b"").hexdigest()
SUBPROJECT = "riao/ria1"


def _corpusjson(data: Path) -> Path:
    root = data / SUBPROJECT / "corpusjson"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _doc(text_id: str) -> dict[str, object]:
    return {
        "type": "cdl",
        "textid": text_id,
        "cdl": [
            {
                "node": "c",
                "type": "text",
                "id": f"{text_id}.U0",
                "cdl": [
                    {"node": "d", "type": "surface", "ref": "", "label": ""},
                    {
                        "node": "d",
                        "type": "line-start",
                        "ref": f"{text_id}.1",
                        "label": "1",
                    },
                    {
                        "node": "l",
                        "id": f"{text_id}.l1",
                        "f": {
                            "form": "a",
                            "gdl": [{"v": "a", "utf8": "𒀀"}],
                        },
                    },
                ],
            }
        ],
    }


def _write_doc(path: Path, text_id: str) -> None:
    path.write_text(json.dumps(_doc(text_id)), encoding="utf-8")


def test_zero_byte_observation_is_typed_and_never_guesses_filename_identity(tmp_path: Path) -> None:
    data = tmp_path / "data"
    path = _corpusjson(data) / "P999999.json"
    path.write_bytes(b"")

    observation = loader.observe_source(path, data=data)

    assert isinstance(observation, loader.SourceHazard)
    assert observation.kind == "empty-file"
    assert observation.relative_path == "riao/ria1/corpusjson/P999999.json"
    assert observation.subproject == SUBPROJECT
    assert observation.bytes == 0
    assert observation.sha256 == EMPTY_SHA256
    assert observation.source_id is None


def test_invalid_utf8_json_root_and_missing_identity_are_distinct_hazards(tmp_path: Path) -> None:
    data = tmp_path / "data"
    root = _corpusjson(data)
    cases = (
        ("Q1.json", b"\xff", "invalid-utf8"),
        ("Q2.json", b"{broken", "invalid-json"),
        ("Q3.json", b"[]", "non-object-json"),
        ("Q4.json", b'{"type":"cdl","cdl":[]}', "missing-source-id"),
    )

    observed = []
    for name, payload, expected_kind in cases:
        path = root / name
        path.write_bytes(payload)
        result = loader.observe_source(path, data=data)
        assert isinstance(result, loader.SourceHazard)
        assert result.kind == expected_kind
        assert result.source_id is None
        assert result.bytes == len(payload)
        assert result.sha256 == sha256(payload).hexdigest()
        observed.append(result)

    assert len({item.kind for item in observed}) == 4


def test_readable_source_uses_embedded_identity_not_filename(tmp_path: Path) -> None:
    data = tmp_path / "data"
    path = _corpusjson(data) / "Q999999.json"
    _write_doc(path, "Q000123")

    observation = loader.observe_source(path, data=data)

    assert isinstance(observation, loader.ReadableSource)
    assert observation.edition.text_id == "Q000123"
    assert observation.edition.key == f"{SUBPROJECT}:Q000123"
    assert observation.relative_path.endswith("Q999999.json")
    assert loader.load_edition(path).text_id == "Q000123"


def test_duplicate_embedded_identity_is_hard_ambiguity_even_when_skipping(tmp_path: Path) -> None:
    data = tmp_path / "data"
    root = _corpusjson(data)
    _write_doc(root / "a.json", "Q000123")
    _write_doc(root / "b.json", "Q000123")

    with pytest.raises(loader.DuplicateSourceIdentityError):
        list(loader.iter_source_observations(data, subprojects=[SUBPROJECT]))
    with pytest.raises(loader.DuplicateSourceIdentityError):
        list(loader.iter_editions(data, subprojects=[SUBPROJECT], skip_unreadable=True))


def test_skip_compatibility_preserves_readable_order_and_complete_hazard_stream(tmp_path: Path) -> None:
    data = tmp_path / "data"
    root = _corpusjson(data)
    _write_doc(root / "a.json", "Q000001")
    (root / "b.json").write_bytes(b"")
    _write_doc(root / "c.json", "Q000003")

    observations = list(loader.iter_source_observations(data, subprojects=[SUBPROJECT]))
    readable = [item.edition for item in observations if isinstance(item, loader.ReadableSource)]
    hazards = [item for item in observations if isinstance(item, loader.SourceHazard)]
    skipped = list(loader.iter_editions(data, subprojects=[SUBPROJECT], skip_unreadable=True))

    assert [edition.text_id for edition in readable] == ["Q000001", "Q000003"]
    assert [edition.text_id for edition in skipped] == ["Q000001", "Q000003"]
    assert len(hazards) == 1
    assert hazards[0].kind == "empty-file"
    assert hazards[0].relative_path.endswith("b.json")

    with pytest.raises(loader.EmptySourceError):
        list(loader.iter_editions(data, subprojects=[SUBPROJECT], skip_unreadable=False))


def test_hazard_manifest_is_canonical_and_path_stable(tmp_path: Path) -> None:
    data = tmp_path / "data"
    root = _corpusjson(data)
    first = root / "a.json"
    second = root / "b.json"
    first.write_bytes(b"")
    second.write_bytes(b"{broken")
    hazards = tuple(
        item
        for item in loader.iter_source_observations(data, subprojects=[SUBPROJECT])
        if isinstance(item, loader.SourceHazard)
    )

    payload = loader.canonical_hazard_bytes(hazards)
    decoded = json.loads(payload)

    assert payload == loader.canonical_hazard_bytes(hazards)
    assert payload.endswith(b"\n")
    assert decoded["schema_version"] == 1
    assert [item["relative_path"] for item in decoded["hazards"]] == [
        "riao/ria1/corpusjson/a.json",
        "riao/ria1/corpusjson/b.json",
    ]
    assert str(tmp_path) not in payload.decode("utf-8")


def test_survey_reuses_typed_observations_and_preserves_compatibility_paths(tmp_path: Path) -> None:
    data = tmp_path / "data"
    root = _corpusjson(data)
    _write_doc(root / "good.json", "Q000001")
    bad = root / "bad.json"
    bad.write_bytes(b"")

    result = loader.survey(data, subprojects=[SUBPROJECT])

    assert result.source_files == 2
    assert result.parseable == 1
    assert result.unreadable == 1
    assert result.unreadable_paths == (bad,)
    assert len(result.hazards) == 1
    assert result.hazards[0].kind == "empty-file"
    assert result.hazards[0].relative_path == "riao/ria1/corpusjson/bad.json"


def test_full_build_reconciles_source_members_with_typed_omissions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = tmp_path / "data"
    root = _corpusjson(data)
    _write_doc(root / "good.json", "Q000001")
    (root / "empty.json").write_bytes(b"")
    monkeypatch.setattr(metadata, "load_index", lambda _data: metadata.MetadataIndex.empty())

    report = corpus.build_full_tf(tmp_path / "tf", data=data)

    assert report.documents == 1
    assert report.source_members == 2
    assert report.readable_source_members == 1
    assert report.unreadable_source_members == 1
    assert report.source_members == report.readable_source_members + report.unreadable_source_members
    assert report.documents == report.readable_source_members
    assert len(report.source_hazards) == 1
    assert report.source_hazards[0].kind == "empty-file"
    assert report.source_hazards[0].relative_path == "riao/ria1/corpusjson/empty.json"


def test_observation_preserves_full_deep_corpusjson_tree_context(tmp_path: Path) -> None:
    data = tmp_path / "data"
    root = data / "aemw" / "alalakh" / "idrimi" / "corpusjson"
    root.mkdir(parents=True)
    path = root / "P999999.json"
    path.write_bytes(b"")

    observation = loader.observe_source(path, data=data)

    assert isinstance(observation, loader.SourceHazard)
    assert observation.subproject == "aemw/alalakh/idrimi"
    assert observation.relative_path == "aemw/alalakh/idrimi/corpusjson/P999999.json"


def test_canonical_hazard_bytes_are_independent_of_caller_order(tmp_path: Path) -> None:
    data = tmp_path / "data"
    root = _corpusjson(data)
    first = root / "a.json"
    second = root / "b.json"
    first.write_bytes(b"")
    second.write_bytes(b"{broken")
    hazards = [
        loader.observe_source(first, data=data),
        loader.observe_source(second, data=data),
    ]
    assert all(isinstance(item, loader.SourceHazard) for item in hazards)

    assert loader.canonical_hazard_bytes(hazards) == loader.canonical_hazard_bytes(
        tuple(reversed(hazards))
    )


def test_low_level_build_does_not_misreport_unknown_source_accounting_as_zero(tmp_path: Path) -> None:
    data = tmp_path / "data"
    root = _corpusjson(data)
    path = root / "good.json"
    _write_doc(path, "Q000001")
    edition = loader.load_edition(path)

    report = corpus.build_tf(
        tmp_path / "tf",
        editions=(edition,),
        metadata_index=metadata.MetadataIndex.empty(),
    )

    assert report.documents == 1
    assert report.source_members is None
    assert report.readable_source_members is None
    assert report.unreadable_source_members is None
    assert report.source_hazards is None
    assert "source members" not in report.report()
