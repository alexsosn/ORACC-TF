"""Source-grounded RED tests for two real ETCSRI nonw CDL events (issue #32).

Unlike missing LINE spans (nonx), nonw events are not words and carry no GDL.
Preserve both an empty original ref and a nonempty source ref losslessly.
"""
from __future__ import annotations

from hashlib import sha1
import json
from pathlib import Path

import pytest
from tf.fabric import Fabric

from oracc_tf import etcsri, paths


WITNESSES = (
    ("Q001794", "286a599b1331f437ca1fa0bbb22e16053206056e",
     "Q001794.U4", {"node": "d", "type": "nonw", "ref": ""}),
    ("Q001870", "f8ad81e0619d52123b9be24848aeb9af3d7f709d",
     "Q001870.U2",
     {"node": "d", "type": "nonw", "ref": "Q001870.3.1.a", "lang": "sux"}),
)


def source_witness(tmp_path: Path, witness: tuple) -> tuple[Path, dict, dict]:
    textid, expected_blob, source_sentence, expected_marker = witness
    src = paths.DATA / "etcsri" / "corpusjson" / f"{textid}.json"
    raw = src.read_bytes()
    actual = sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
    assert actual == expected_blob, "real source witness changed: inspect upstream"
    root = json.loads(raw)
    assert root["textid"] == textid and root["project"] == "etcsri"

    # Retain the original sentence and its actual enclosing source hierarchy.
    text, = [c for c in root["cdl"] if c.get("node") == "c" and c.get("type") == "text"]
    discourse, = [c for c in text["cdl"] if c.get("node") == "c" and c.get("type") == "discourse"]
    sentence, = [
        c for c in discourse["cdl"]
        if c.get("node") == "c" and c.get("id") == source_sentence
    ]
    markers = [c for c in sentence["cdl"] if c.get("node") == "d" and c.get("type") == "nonw"]
    assert markers == [expected_marker]
    root["cdl"] = [text]
    text["cdl"] = [discourse]
    discourse["cdl"] = [sentence]
    changed = tmp_path / f"{textid}.json"
    changed.write_text(json.dumps(root, ensure_ascii=False), encoding="utf-8")
    return changed, root, markers[0]


@pytest.mark.corpus
@pytest.mark.parametrize("witness", WITNESSES, ids=["blank-ref-Q001794", "sux-ref-Q001870"])
def test_real_nonword_marker_is_not_word_line_or_semantic_sign(tmp_path: Path, witness: tuple) -> None:
    path, source, marker = source_witness(tmp_path, witness)
    # Real source sentence contains nested phrase chunks. Census every CDL
    # descendant, not just immediate sentence children.
    pending = [source["cdl"][0]["cdl"][0]["cdl"][0]]
    expected_words = 0
    expected_lines = 0
    while pending:
        entry = pending.pop()
        expected_words += entry.get("node") == "l"
        expected_lines += entry.get("node") == "d" and entry.get("type") == "line-start"
        pending.extend(entry.get("cdl") or [])
    report = etcsri.build_tf(tmp_path / "tf", source_paths=[path])
    assert report.words == expected_words
    assert report.lines == expected_lines
    tf = Fabric(locations=str(tmp_path / "tf"), silent="deep")
    assert tf.loadAll(silent="deep")
    api = tf.api
    assert api is not None
    nodes = api.F.otype.s("nonword_marker")
    assert len(nodes) == 1
    n = nodes[0]
    assert api.F.marker_type.v(n) == "nonw"
    assert json.loads(api.F.marker_json.v(n)) == marker
    assert api.F.source_ref_json.v(n) == json.dumps(marker["ref"], ensure_ascii=False)
    if "lang" in marker:
        assert api.F.marker_lang.v(n) == marker["lang"]
    else:
        # A single-document TF may omit an entirely unpopulated feature file.
        assert not hasattr(api.F, "marker_lang") or api.F.marker_lang.v(n) is None
    slot, = api.L.d(n, otype="sign")
    assert api.F.synthetic.v(slot) == 1
    assert api.F.utf8.v(slot) is None
    assert all(slot not in api.L.d(x, otype="sign") for x in api.F.otype.s("line"))
    parent, = api.E.chunk_parent.f(n)
    assert api.F.source_id.v(parent) == witness[2]


@pytest.mark.parametrize("mutation", [
    {"ref": 99}, {"lang": 7}, {"unexpected_field": "does not belong"}
])
def test_nonword_marker_rejects_corrupt_source_shape(tmp_path: Path, mutation: dict) -> None:
    path, source, marker = source_witness(tmp_path, WITNESSES[1])
    marker.update(mutation)
    path.write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(etcsri.ETCSRISourceError, match="nonw|marker|ref|lang"):
        etcsri.build_tf(tmp_path / "tf", source_paths=[path])
