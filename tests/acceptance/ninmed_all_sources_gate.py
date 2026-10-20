"""P-008 follow-up: complete native ORACC NINMED TF acceptance (heavy opt-in test).

Not collected by default pytest file patterns: explicit dedicated workflow only.
Ground truth: the 159 *readable* primary corpusjson bodies and one known empty
P395407 source hazard, not the textually divergent Nino TF edition.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import resource
import time

import pytest
from tf.fabric import Fabric

from oracc_tf import ninmed, paths


SRC = paths.DATA / "asbp" / "ninmed" / "corpusjson"
GDL_CHILDREN = ("group", "seq", "qualified", "mods")


def _source_words(doc: dict):
    pending = [doc]
    while pending:
        node = pending.pop()
        if node.get("node") == "l":
            yield node
        pending.extend(node.get("cdl") or [])


def _independent_source_signs(entries: list[dict]):
    """R-007 source-sign census rules, separate from the converter classifier."""
    for item in entries:
        child_keys = [k for k in GDL_CHILDREN if k in item]
        if child_keys and item.get("utf8"):
            yield item
        elif child_keys:
            for child_key in child_keys:
                yield from _independent_source_signs(item[child_key])
        elif any(k in item for k in ("v", "s", "x")):
            yield item


def _members() -> list[Path]:
    files = sorted(SRC.glob("*.json"))
    assert len(files) == 160, "ORACC NINMED primary source membership drift"
    hazards = [p.name for p in files if p.stat().st_size == 0]
    assert hazards == ["P395407.json"], f"Unexpected unreadable source partition: {hazards}"
    return [p for p in files if p.stat().st_size > 0]


def test_zero_byte_source_is_a_recorded_hazard_not_an_empty_edition(tmp_path: Path) -> None:
    members = _members()
    assert len(members) == 159
    with pytest.raises(ninmed.NINMEDSourceError, match="unreadable"):
        ninmed.build_tf(
            tmp_path / "reject", source_paths=[SRC / "P395407.json"],
        )


def test_every_readable_oracc_ninmed_body_roundtrips_into_native_tf(tmp_path: Path) -> None:
    members = _members()
    assert len(members) == 159
    started = time.perf_counter()
    root = tmp_path / "tf"
    report = ninmed.build_tf(root, source_paths=members)
    build_seconds = time.perf_counter() - started
    print(f"NINMED full TF build wall seconds: {build_seconds:.3f}")
    print(f"NINMED full TF peak process RSS KiB: {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}")
    print(f"NINMED full TF disk bytes: {sum(p.stat().st_size for p in root.rglob('*.tf'))}")
    assert report.documents == 159
    assert report.words == 65089
    assert report.sign_word_membership_errors == 0
    assert report.word_line_membership_errors == 0

    fabric = Fabric(locations=str(root), silent="deep")
    assert fabric.loadAll(silent="deep")
    api = fabric.api
    assert api is not None
    documents = {
        api.F.document_key.v(n): n for n in api.F.otype.s("document")
    }
    tf_words = {
        (api.F.document_key.v(n), api.F.source_id.v(n)): n
        for n in api.F.otype.s("word")
    }
    assert len(documents) == 159
    assert len(tf_words) == 65089, "A duplicate TF source identity was collapsed"

    observed_ids: set[tuple[str, str]] = set()
    source_signs = 0
    source_forms = Counter()
    for path in members:
        raw = path.read_bytes()
        doc = json.loads(raw)
        assert doc["project"] == "asbp/ninmed"
        key = f"asbp/ninmed:{doc['textid']}"
        node = documents[key]
        assert api.F.source_sha256.v(node) == sha256(raw).hexdigest()
        assert json.loads(api.F.document_meta_json.v(node)) == {
            k: v for k, v in doc.items() if k != "cdl"
        }
        for word in _source_words(doc):
            source_id = word["id"]
            identity = key, source_id
            assert identity not in observed_ids, f"duplicate source word: {identity}"
            observed_ids.add(identity)
            tf_word = tf_words[identity]
            assert json.loads(api.F.word_json.v(tf_word)) == word, identity
            f = word.get("f") or {}
            for field in ("form", "cf", "gw", "pos"):
                assert getattr(api.F, field).v(tf_word) == f.get(field), (
                    identity, field
                )
            signs = list(_independent_source_signs(f.get("gdl") or []))
            source_signs += len(signs)
            if f.get("cf"):
                source_forms[f["cf"]] += 1
    assert set(tf_words) == observed_ids
    assert len(observed_ids) == 65089
    assert source_signs == report.signs, "semantic sign loss/inflation against independent GDL census"
    assert len(api.F.otype.s("sign")) == report.signs + report.synthetic_slots
    assert source_forms["DÙ.DÙ.BI"] > 0
    assert not (root / "uniqueLemma.tf").exists(), "Nino model must not leak into ORACC"
