"""RED-first source-identity acceptance tests for the ORACC loader.

Loader-observed editions must meet downstream word/lexeme identity contracts.
These are synthetic source mutations, not claims about pinned RIAO/RINAP data.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

from oracc_tf import loader


SUBPROJECT = "riao/ria1"


def _root(data: Path) -> Path:
    corpusjson = data / SUBPROJECT / "corpusjson"
    corpusjson.mkdir(parents=True, exist_ok=True)
    return corpusjson


def _edition(text_id: str, word_ids: list[object]) -> dict:
    return {
        "type": "cdl",
        "textid": text_id,
        "cdl": [
            {
                "node": "c", "type": "text", "id": f"{text_id}.U0",
                "cdl": [
                    {"node": "d", "type": "line-start", "ref": f"{text_id}.1"},
                    *[
                        {"node": "l", "id": word_id, "f": {"gdl": []}}
                        if word_id is not _MISSING else
                        {"node": "l", "f": {"gdl": []}}
                        for word_id in word_ids
                    ],
                ],
            }
        ],
    }


_MISSING = object()


@pytest.mark.parametrize("word_ids", [
    [_MISSING],
    [None],
    [""],
    ["  "],
    [42],
    [["list-id"]],
    ["duplicate", "duplicate"],
])
def test_bad_word_ids_are_auditable_source_hazards(
    tmp_path: Path, word_ids: list[object],
) -> None:
    data = tmp_path / "data"
    path = _root(data) / "Q000123.json"
    doc = _edition("Q000123", word_ids)
    payload = json.dumps(doc, ensure_ascii=False).encode("utf-8")
    path.write_bytes(payload)

    with pytest.raises(loader.InvalidWordIdentitySource):
        loader.count_words(doc)

    observation = loader.observe_source(path, data=data)
    assert isinstance(observation, loader.SourceHazard)
    assert observation.kind == "invalid-word-identity"
    assert observation.source_id == "Q000123"
    assert observation.subproject == SUBPROJECT
    assert observation.bytes == len(payload)
    assert observation.sha256 == sha256(payload).hexdigest()
    assert observation.relative_path == "riao/ria1/corpusjson/Q000123.json"

    with pytest.raises(loader.UnparseableSourceError, match="invalid-word-identity"):
        loader.load_edition(path)

    # Omission stays visible in the observation stream while the caller can
    # explicitly skip the malformed member to continue a corpus survey.
    assert [item.kind for item in loader.iter_source_observations(
        data, subprojects=[SUBPROJECT],
    ) if isinstance(item, loader.SourceHazard)] == ["invalid-word-identity"]
    assert list(loader.iter_editions(
        data, subprojects=[SUBPROJECT], skip_unreadable=True,
    )) == []


def test_word_identity_uniqueness_is_per_edition_not_global(tmp_path: Path) -> None:
    data = tmp_path / "data"
    root = _root(data)
    for text_id in ("Q000123", "Q000124"):
        (root / f"{text_id}.json").write_text(
            json.dumps(_edition(text_id, ["reused.word", "unique." + text_id])),
            encoding="utf-8",
        )

    editions = list(loader.iter_editions(
        data, subprojects=[SUBPROJECT], skip_unreadable=False,
    ))
    assert [edition.text_id for edition in editions] == ["Q000123", "Q000124"]
    assert [edition.word_count for edition in editions] == [2, 2]


def test_valid_ids_preserve_embedded_spelling_without_normalisation() -> None:
    doc = _edition("Q000125", [" Q000125.l1 ", "Q000125.l2"])
    assert loader.count_words(doc) == 2


def test_invalid_cdl_remains_structural_hazard_not_word_identity(tmp_path: Path) -> None:
    data = tmp_path / "data"
    path = _root(data) / "Q000125.json"
    path.write_text(
        json.dumps({"textid": "Q000125", "type": "cdl", "cdl": False}),
        encoding="utf-8",
    )
    observed = loader.observe_source(path, data=data)
    assert isinstance(observed, loader.SourceHazard)
    assert observed.kind == "invalid-cdl"
