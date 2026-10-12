"""Issue #32 RED: source-native nonx missing-line markers are not words or signs.

The witness is the actual Q000377.U490 sentence, extracted directly from the
checked-in 10 MB ORACC edition; metadata and marker are not hand-authored.
"""
from __future__ import annotations

import json
from hashlib import sha1
from pathlib import Path

import pytest
from tf.fabric import Fabric

from oracc_tf import etcsri, paths

SOURCE = paths.DATA / "etcsri" / "corpusjson" / "Q000377.json"


def _source_witness(tmp_path: Path) -> tuple[Path, dict, dict]:
    raw = SOURCE.read_bytes()
    blob_sha = sha1(b"blob " + str(len(raw)).encode("ascii") + bytes([0]) + raw).hexdigest()
    assert blob_sha == "62bbca48a50205353ac5ed8225a3ce3e163c5f31", "real ETCSRI source changed"
    source = json.loads(raw)
    assert source["project"] == "etcsri"
    assert source["textid"] == "Q000377"
    root = source["cdl"][0]
    discourse = root["cdl"][0]
    assert root["id"] == "Q000377.U0" and discourse["id"] == "Q000377.U1"
    sentence = next(x for x in discourse["cdl"] if x.get("id") == "Q000377.U490")
    assert sentence["type"] == "sentence"
    markers = [x for x in sentence["cdl"] if x.get("node") == "d"]
    gap, = [x for x in markers if x.get("type") == "nonx"]
    assert gap == {
        "node": "d", "type": "nonx", "ref": "Q000377.387",
        "strict": "1", "extent": "3", "scope": "line", "state": "missing",
    }
    assert [x["ref"] for x in markers if x["type"] == "line-start"] == [
        "Q000377.385", "Q000377.386", "Q000377.388", "Q000377.389",
    ]
    discourse["cdl"] = [sentence]
    root["cdl"] = [discourse]
    source["cdl"] = [root]
    path = tmp_path / "Q000377.json"
    path.write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")
    return path, source, gap


@pytest.mark.corpus
def test_real_q000377_nonx_is_explicit_technical_gap_without_fabricated_lines(tmp_path: Path) -> None:
    path, _, gap = _source_witness(tmp_path)
    report = etcsri.build_tf(tmp_path / "tf", source_paths=[path])
    assert report.documents == 1
    assert report.lines == 4  # extent=3 is source markup, NOT three invented lines
    tf = Fabric(locations=str(tmp_path / "tf"), silent="deep")
    assert tf.loadAll(silent="deep")
    api = tf.api
    assert api is not None
    gaps = api.F.otype.s("missing_span")
    assert len(gaps) == 1
    node = gaps[0]
    assert api.F.source_id.v(node) == "Q000377.387"
    assert api.F.marker_type.v(node) == "nonx"
    assert api.F.gap_scope.v(node) == "line"
    assert api.F.gap_state.v(node) == "missing"
    assert api.F.gap_extent.v(node) == "3"
    assert api.F.gap_strict.v(node) == "1"
    assert json.loads(api.F.marker_json.v(node)) == gap
    slots = api.L.d(node, otype="sign")
    assert len(slots) == 1
    slot = slots[0]
    assert api.F.synthetic.v(slot) == 1
    assert api.F.utf8.v(slot) is None
    assert all(
        slot not in api.L.d(line, otype="sign")
        for line in api.F.otype.s("line")
    )
    sentence = next(
        n for n in api.F.otype.s("sentence")
        if api.F.source_id.v(n) == "Q000377.U490"
    )
    assert tuple(api.E.chunk_parent.f(node)) == (sentence,)
    assert slot in api.L.d(sentence, otype="sign")


@pytest.mark.corpus
@pytest.mark.parametrize("change", [
    {"extent": "0"},
    {"extent": "three"},
    {"scope": "word"},
    {"state": "uncertain"},
])
def test_real_q000377_nonx_invalid_semantics_fail_closed(tmp_path: Path, change: dict) -> None:
    path, source, gap = _source_witness(tmp_path)
    gap.update(change)
    path.write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(etcsri.ETCSRISourceError, match="nonx|missing|extent|scope|state"):
        etcsri.build_tf(tmp_path / "tf", source_paths=[path])


@pytest.mark.corpus
def test_repeated_real_q000377_nonx_reference_is_not_silently_admitted(tmp_path: Path) -> None:
    path, source, gap = _source_witness(tmp_path)
    sentence = source["cdl"][0]["cdl"][0]["cdl"][0]
    assert sentence["id"] == "Q000377.U490"
    sentence["cdl"].insert(sentence["cdl"].index(gap), dict(gap))
    path.write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(etcsri.ETCSRISourceError, match="duplicate nonx"):
        etcsri.build_tf(tmp_path / "tf", source_paths=[path])
