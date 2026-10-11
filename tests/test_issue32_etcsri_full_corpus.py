"""Issue #32 whole-corpus acceptance: source census -> actual TF graph.

This intentionally starts RED: unlike P-007's two witnesses, all 1,456
checked-in ETCSRI editions must survive the same source-to-TF path. Do not
'fix' a failing source by excluding editions or by fabricating annotations.
Historical expectations are pinned to R-007's 2026-10-11 working-tree census.
"""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

import pytest
from tf.fabric import Fabric

from oracc_tf import etcsri, gdl, paths


@pytest.mark.corpus
def test_all_checked_in_etcsri_source_editions_build_and_roundtrip(tmp_path: Path) -> None:
    source_dir = paths.DATA / "etcsri" / "corpusjson"
    members = sorted(source_dir.glob("*.json"))
    assert len(members) == 1456, "R-007 source membership changed; inspect upstream delta"

    report = etcsri.build_tf(tmp_path / "tf", source_paths=members)
    assert report.documents == 1456
    assert report.words == 29573
    assert report.semantic_signs == 68403
    assert report.tf_node_counts["document"] == 1456
    assert report.tf_node_counts["word"] == 29573

    tf = Fabric(locations=str(tmp_path / "tf"), silent="deep")
    assert tf.loadAll(silent="deep"), "full ETCSRI graph must be loadable as TF"
    api = tf.api
    assert api is not None

    document_keys = {
        api.F.document_key.v(n) for n in api.F.otype.s("document")
    }
    assert len(document_keys) == 1456
    assert "etcsri:Q000935" in document_keys
    assert "etcsri:Q000376" in document_keys

    word_features = Counter()
    for node in api.F.otype.s("word"):
        if api.F.morph.v(node):
            word_features["morph"] += 1
        if api.F.morph2.v(node):
            word_features["morph2"] += 1
        if api.F.para_json.v(node) and json.loads(api.F.para_json.v(node)):
            word_features["para"] += 1
    assert word_features == {
        "morph": 28180,
        "morph2": 28180,
        "para": 3584,
    }, "the recorded R-007 source annotation census must remain queryable"

    # Whole-source semantic round-trip, not merely parity of summary counts.
    tf_documents = {
        api.F.document_key.v(n): n for n in api.F.otype.s("document")
    }
    tf_words = {
        (api.F.document_key.v(n), api.F.source_id.v(n)): n
        for n in api.F.otype.s("word")
    }
    assert len(tf_words) == 29573, "duplicate TF word identity collapsed"
    observed_source_keys: set[tuple[str, str]] = set()
    for path in members:
        raw = path.read_bytes()
        doc = json.loads(raw)
        document_key = f"etcsri:{doc['textid']}"
        doc_node = tf_documents[document_key]
        assert api.F.source_sha256.v(doc_node) == sha256(raw).hexdigest()
        assert json.loads(api.F.source_meta_json.v(doc_node)) == {
            key: value for key, value in doc.items() if key != "cdl"
        }
        linkbases = [entry["linkbase"] for entry in doc["cdl"] if "linkbase" in entry]
        assert len(linkbases) <= 1, f"ambiguous source linkbase: {document_key}"
        assert (
            json.loads(api.F.linkbase_json.v(doc_node))
            if api.F.linkbase_json.v(doc_node) is not None else None
        ) == (linkbases[0] if linkbases else None)
        pending = list(reversed(doc["cdl"]))
        while pending:
            entry = pending.pop()
            if entry.get("node") == "l":
                key = (document_key, entry["id"])
                assert key not in observed_source_keys, f"duplicate source word {key}"
                observed_source_keys.add(key)
                tf_word = tf_words[key]
                assert json.loads(api.F.word_json.v(tf_word)) == entry
                assert json.loads(api.F.f_json.v(tf_word)) == entry["f"]
                for feat in ("base", "morph", "morph2"):
                    assert getattr(api.F, feat).v(tf_word) == entry["f"].get(feat), (
                        key, feat
                    )
                for source_key, tf_feature in (
                    ("para", "para_json"), ("props", "props_json")
                ):
                    expected = entry.get(source_key)
                    serialized = getattr(api.F, tf_feature).v(tf_word)
                    assert (json.loads(serialized) if serialized is not None else None) == expected, (
                        key, tf_feature
                    )
                sign_view = tuple(gdl.signs(entry["f"].get("gdl", []), word_id=entry["id"]))
                tf_signs = tuple(
                    sign for sign in api.L.d(tf_word, otype="sign")
                    if api.F.synthetic.v(sign) != 1
                )
                assert len(sign_view) == len(tf_signs), f"word sign count mismatch: {key}"
                for original, sign in zip(sign_view, tf_signs, strict=True):
                    assert api.F.src_path.v(sign) == original.src_path, key
                    assert json.loads(api.F.sign_json.v(sign)) == original.value, key
                    assert api.F.utf8.v(sign) == original.value.get("utf8"), key
            if "cdl" in entry:
                pending.extend(reversed(entry["cdl"]))
    assert set(tf_words) == observed_source_keys

    semantic_slots = [
        sign for sign in api.F.otype.s("sign")
        if api.F.synthetic.v(sign) != 1
    ]
    assert len(semantic_slots) == report.semantic_signs
    assert len(api.F.otype.s("sign")) == report.semantic_signs + report.synthetic_slots
    assert sum(bool(api.F.utf8.v(n)) for n in semantic_slots) == 67624
