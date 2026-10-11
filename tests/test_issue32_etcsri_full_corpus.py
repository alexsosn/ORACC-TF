"""Issue #32 whole-corpus acceptance: source census -> actual TF graph.

This intentionally starts RED: unlike P-007's two witnesses, all 1,456
checked-in ETCSRI editions must survive the same source-to-TF path. Do not
'fix' a failing source by excluding editions or by fabricating annotations.
Historical expectations are pinned to R-007's 2026-10-11 working-tree census.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest
from tf.fabric import Fabric

from oracc_tf import etcsri, paths


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
        if api.F.morph.v(node) is not None:
            word_features["morph"] += 1
        if api.F.morph2.v(node) is not None:
            word_features["morph2"] += 1
        if api.F.para_json.v(node) is not None:
            word_features["para"] += 1
    assert word_features == {
        "morph": 28180,
        "morph2": 28180,
        "para": 3584,
    }, "the recorded R-007 source annotation census must remain queryable"

    semantic_slots = [
        sign for sign in api.F.otype.s("sign")
        if api.F.synthetic.v(sign) != 1
    ]
    assert len(semantic_slots) == report.semantic_signs
    assert len(api.F.otype.s("sign")) == report.semantic_signs + report.synthetic_slots
    assert sum(api.F.utf8.v(n) is not None for n in semantic_slots) == 67624
