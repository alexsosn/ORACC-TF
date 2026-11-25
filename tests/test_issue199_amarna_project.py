"""Source-based RED gates for AEMW Amarna's existing-graph conversion.

The small positive fixtures are original ORACC editions, not invented text.
The whole-source test compares raw CDL against the loaded TF graph without
using the converter's word traversal as its oracle.
"""
from __future__ import annotations

from hashlib import sha1, sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from oracc_tf import corpus, paths

SOURCE = paths.DATA / "aemw" / "amarna"
PROJECT = "aemw/amarna"
BLOBS = {
    "P270838": "8e46585be0e7ca394e28e219b6351cf2a74a5381",
    "P270875": "424dd459703fd6bb78956fdc88c424eccbc725ef",
}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def raw_words(doc):
    pending = [doc]
    while pending:
        obj = pending.pop()
        if obj.get("node") == "l":
            yield obj
        pending.extend(reversed(obj.get("cdl") or []))


def snapshot(tmp_path):
    root = tmp_path / "input"
    (root / "corpusjson").mkdir(parents=True)
    manifest = read(SOURCE / "corpus.json")
    manifest["members"] = {
        key: manifest["members"][key] for key in BLOBS
    }
    (root / "corpus.json").write_text(json.dumps(manifest), encoding="utf-8")
    # The catalogue deliberately contains entries without exported CDL.
    shutil.copyfile(SOURCE / "catalogue.json", root / "catalogue.json")
    for key, blob in BLOBS.items():
        path = SOURCE / "corpusjson" / f"{key}.json"
        payload = path.read_bytes()
        assert sha1(f"blob {len(payload)}\0".encode() + payload).hexdigest() == blob
        shutil.copyfile(path, root / "corpusjson" / path.name)
    return root


def invoke(root, output):
    return subprocess.run(
        [sys.executable, "-m", "oracc_tf", "build-project",
         "--project", PROJECT, "--source-dir", str(root), "--output", str(output)],
        text=True, capture_output=True, check=False, cwd=root.parent,
    )


def check_source_to_tf(root, output):
    manifest = read(root / "corpus.json")["members"]
    catalogue = read(root / "catalogue.json")["members"]
    api = corpus.load_tf(output)
    documents = {
        api.F.text_id.v(node): node for node in api.F.otype.s("document")
    }
    assert len(documents) == len(api.F.otype.s("document"))
    assert set(documents) == set(manifest)
    actual_words = {
        (api.F.document_key.v(n), api.F.source_id.v(n)): n
        for n in api.F.otype.s("word")
    }
    assert len(actual_words) == len(api.F.otype.s("word"))
    expected_words = set()
    languages = set()
    for text_id, relative in manifest.items():
        source = root / relative
        doc = read(source)
        dn = documents[text_id]
        key = f"{PROJECT}:{text_id}"
        assert api.F.document_key.v(dn) == key
        assert api.F.source_sha256.v(dn) == sha256(source.read_bytes()).hexdigest()
        if text_id in catalogue:
            assert api.F.designation.v(dn) == catalogue[text_id].get("designation")
            assert json.loads(api.F.catalogue_json.v(dn)) == catalogue[text_id]
        for raw in raw_words(doc):
            ident = (key, raw["id"])
            assert ident not in expected_words
            expected_words.add(ident)
            node = actual_words[ident]
            assert json.loads(api.F.word_json.v(node)) == raw
            features = raw.get("f") or {}
            for f in ("lang", "form", "cf", "gw", "pos"):
                assert api.Fs(f).v(node) == features.get(f)
            if features.get("lang"):
                languages.add(features["lang"])
            assert api.L.u(node, otype="document") == (dn,)
    assert set(actual_words) == expected_words
    assert "qca" in languages and "akk-x-mbperi" in languages
    assert "P271214" not in documents  # EA 24 exists in catalogue only.
    return api


def test_amarna_local_cli_real_multilingual_letters(tmp_path):
    root = snapshot(tmp_path)
    output = tmp_path / "tf"
    run = invoke(root, output)
    assert run.returncode == 0, run.stderr
    api = check_source_to_tf(root, output)
    hits = api.S.search("word lang=qca cf=ʿšr", silent="deep")
    assert any(api.F.source_id.v(row[0]) == "P270838.l0003b" for row in hits)


@pytest.mark.parametrize("hazard", ["missing", "extra", "foreign", "wrong-id", "path"])
def test_amarna_manifest_rejects_unaccounted_or_foreign_input(tmp_path, hazard):
    root = snapshot(tmp_path)
    source = root / "corpusjson" / "P270838.json"
    if hazard == "missing":
        source.unlink()
    elif hazard == "extra":
        shutil.copyfile(source, source.with_name("P999999.json"))
    elif hazard in {"foreign", "wrong-id"}:
        doc = read(source)
        if hazard == "foreign":
            doc["project"] = "aemw/ugarit"
        else:
            doc["textid"] = "P999999"
        source.write_text(json.dumps(doc), encoding="utf-8")
    else:
        manifest = read(root / "corpus.json")
        manifest["members"]["P270838"] = "../P270838.json"
        (root / "corpus.json").write_text(json.dumps(manifest), encoding="utf-8")
    output = tmp_path / "tf"
    run = invoke(root, output)
    assert run.returncode != 0
    assert not (output / "otype.tf").exists()


@pytest.mark.corpus
def test_full_pinned_amarna_export_conservation(tmp_path):
    output = tmp_path / "tf"
    manifest = read(SOURCE / "corpus.json")
    assert len(manifest["members"]) == 305
    assert len(read(SOURCE / "catalogue.json")["members"]) == 379
    run = invoke(SOURCE, output)
    assert run.returncode == 0, run.stderr
    check_source_to_tf(SOURCE, output)
