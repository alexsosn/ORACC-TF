"""RED-first: source survey must never admit words invisible to sections.

ORACC word (l) and marker (d) event nodes are leaf events for the
section walker. Nonempty nested CDL below them must not be silently ignored.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

from oracc_tf import loader, sections


def _doc() -> dict:
    return {
        "type": "cdl",
        "textid": "QLEAF",
        "cdl": [{
            "node": "c", "type": "text", "id": "QLEAF.U0",
            "cdl": [
                {"node": "d", "type": "surface", "ref": "", "label": ""},
                {"node": "d", "type": "line-start", "ref": "QLEAF.1", "label": "1"},
                {"node": "l", "id": "QLEAF.l1", "f": {"form": "a", "gdl": []}},
            ],
        }],
    }


def _write(data: Path, doc: dict) -> tuple[Path, bytes]:
    path = data / "riao/ria1/corpusjson/QLEAF.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")
    path.write_bytes(payload)
    return path, payload


@pytest.mark.parametrize("leaf_kind", ["l", "d"])
def test_leaf_with_nested_word_is_hazard_not_silently_discarded(
    tmp_path: Path, leaf_kind: str
) -> None:
    doc = _doc()
    line = doc["cdl"][0]["cdl"]
    target = line[-1] if leaf_kind == "l" else line[1]
    target["cdl"] = [{
        "node": "l", "id": "QLEAF.hidden",
        "f": {"form": "hidden", "gdl": []},
    }]
    # The source word walker would count both; the existing section walker
    # otherwise silently omits the nested one, corrupting section mapping.
    path, payload = _write(tmp_path, doc)
    observation = loader.observe_source(path, data=tmp_path)
    assert isinstance(observation, loader.SourceHazard)
    assert observation.kind == "invalid-cdl"
    assert observation.source_id == "QLEAF"
    assert observation.relative_path == "riao/ria1/corpusjson/QLEAF.json"
    assert observation.bytes == len(payload)
    assert observation.sha256 == sha256(payload).hexdigest()
    with pytest.raises(loader.UnparseableSourceError, match="invalid-cdl"):
        loader.load_edition(path)
    with pytest.raises(sections.InvalidSectionSource, match="nonempty 'cdl'.*leaf"):
        sections.walk_document(doc)


@pytest.mark.parametrize("value", ["absent", None, []])
@pytest.mark.parametrize("leaf_kind", ["l", "d"])
def test_empty_or_missing_leaf_cdl_is_backward_compatible(
    tmp_path: Path, leaf_kind: str, value: object
) -> None:
    doc = _doc()
    line = doc["cdl"][0]["cdl"]
    target = line[-1] if leaf_kind == "l" else line[1]
    if value != "absent":
        target["cdl"] = value

    path, _ = _write(tmp_path, doc)
    observation = loader.observe_source(path, data=tmp_path)
    assert isinstance(observation, loader.ReadableSource)
    assert observation.edition.word_count == 1
    walk = sections.walk_document(doc)
    assert walk.source_words == 1
    assert list(walk.word_to_line) == ["QLEAF.l1"]


def test_legal_nested_text_chunks_remain_traversable() -> None:
    doc = _doc()
    doc["cdl"][0]["cdl"].append({
        "node": "c", "type": "phrase", "id": "QLEAF.phrase",
        "cdl": [{"node": "l", "id": "QLEAF.l2", "f": {"form": "b", "gdl": []}}],
    })
    assert loader.count_words(doc) == 2
    walk = sections.walk_document(doc)
    assert walk.source_words == 2
    assert set(walk.word_to_line) == {"QLEAF.l1", "QLEAF.l2"}


@pytest.mark.parametrize("malformed", ["", 0, False, {}, [False]])
@pytest.mark.parametrize("leaf_kind", ["l", "d"])
def test_section_leaf_cdl_shape_is_fail_closed(
    leaf_kind: str, malformed: object
) -> None:
    doc = _doc()
    line = doc["cdl"][0]["cdl"]
    target = line[-1] if leaf_kind == "l" else line[1]
    target["cdl"] = malformed
    with pytest.raises(sections.InvalidSectionSource, match="cdl|child is"):
        sections.walk_document(doc)
