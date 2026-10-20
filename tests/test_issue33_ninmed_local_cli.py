"""Issue #33: RED-first local NINMED wheel/CLI user-facing acceptance.

Each source witness is copied from actual ORACC bytes, pinned by Git blob SHA.
No Nino reference text is imported and no fake word is used as positive data.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

from tf.fabric import Fabric
from oracc_tf import paths


SOURCE_BLOBS = {
    "P285136": "a26ee7550a1f6d62187ef84ab1bfd877b2b",
    "P425685": "4df915aa78b3f701c77c7ee96b6b72708ce4eb29",
}
EMPTY_BLOB = "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"


def _source(tmp_path: Path, *, empty: bool = False) -> Path:
    target = tmp_path / "source" / "corpusjson"
    target.mkdir(parents=True)
    for text_id, digest in SOURCE_BLOBS.items():
        src = paths.DATA / "asbp" / "ninmed" / "corpusjson" / f"{text_id}.json"
        raw = src.read_bytes()
        assert hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == digest
        assert json.loads(raw)["textid"] == text_id
        shutil.copyfile(src, target / src.name)
    if empty:
        src = paths.DATA / "asbp" / "ninmed" / "corpusjson" / "P395407.json"
        raw = src.read_bytes()
        assert hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == EMPTY_BLOB
        shutil.copyfile(src, target / src.name)
    return target


def _invoke(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "oracc_tf", *args],
        cwd=tmp_path, text=True, capture_output=True, check=False,
    )


def test_help_exposes_ninmed_and_explicit_empty_source_flag(tmp_path: Path) -> None:
    r = _invoke(tmp_path, "build-ninmed", "--help")
    assert r.returncode == 0, r.stderr
    for key in ("--source-dir", "--output", "--text-id", "--skip-known-empty"):
        assert key in r.stdout


def test_real_ninmed_local_conversion_and_tf_lexical_query(tmp_path: Path) -> None:
    src = _source(tmp_path)
    out = tmp_path / "tf"
    r = _invoke(tmp_path, "build-ninmed", "--source-dir", str(src.parent), "--output", str(out))
    assert r.returncode == 0, r.stderr
    assert "2 documents" in r.stdout and "376 words" in r.stdout
    tf = Fabric(locations=str(out), silent="deep")
    assert tf.loadAll(silent="deep")
    api = tf.api
    assert api is not None
    words = tuple(api.F.otype.s("word"))
    assert len(words) == 376
    source_word = next(n for n in words if api.F.source_id.v(n) == "P285136.l003f2")
    assert api.F.cf.v(source_word) == "DÙ.DÙ.BI"
    assert api.F.gw.v(source_word) == "ritual (instructions)"
    assert api.F.pos.v(source_word) == "N"
    assert json.loads(api.F.word_json.v(source_word))["id"] == "P285136.l003f2"
    doc_node = next(n for n in api.F.otype.s("document") if api.F.document_key.v(n) == "asbp/ninmed:P285136")
    assert sum(marker["marker"]["type"] == "nonx" for marker in json.loads(api.F.source_markers_json.v(doc_node))) == 8
    lex = api.E.word_lex.f(source_word)
    assert len(lex) == 1
    assert api.F.cf.v(lex[0]) == "DÙ.DÙ.BI"


def test_zero_byte_primary_source_is_explicitly_opted_out(tmp_path: Path) -> None:
    src = _source(tmp_path, empty=True)
    bad = tmp_path / "bad"
    r = _invoke(tmp_path, "build-ninmed", "--source-dir", str(src), "--output", str(bad))
    assert r.returncode != 0
    assert "P395407" in r.stderr and "zero-byte" in r.stderr
    assert not (bad / "otype.tf").exists()
    out = tmp_path / "good"
    r = _invoke(tmp_path, "build-ninmed", "--source-dir", str(src), "--output", str(out), "--skip-known-empty")
    assert r.returncode == 0, r.stderr
    assert "P395407" in r.stdout and "excluded" in r.stdout.lower()
    tf = Fabric(locations=str(out), silent="deep")
    assert tf.loadAll(silent="deep")
    assert len(tf.api.F.otype.s("document")) == 2


def test_unknown_or_renamed_text_id_fails_without_output(tmp_path: Path) -> None:
    src = _source(tmp_path)
    r = _invoke(tmp_path, "build-ninmed", "--source-dir", str(src), "--output", str(tmp_path / "tf"), "--text-id", "P999999")
    assert r.returncode != 0 and "P999999" in r.stderr
    renamed = src / "P285137.json"
    (src / "P285136.json").rename(renamed)
    out = tmp_path / "misidentified"
    r = _invoke(tmp_path, "build-ninmed", "--source-dir", str(src), "--output", str(out), "--text-id", "P285137")
    assert r.returncode != 0 and "P285137" in r.stderr and "P285136" in r.stderr
    assert not (out / "otype.tf").exists()


def test_user_output_is_not_overwritten_or_created_inside_source(tmp_path: Path) -> None:
    src = _source(tmp_path)
    out = tmp_path / "existing"
    out.mkdir()
    (out / "user.txt").write_text("retain", encoding="utf8")
    r = _invoke(tmp_path, "build-ninmed", "--source-dir", str(src), "--output", str(out))
    assert r.returncode != 0
    assert (out / "user.txt").read_text() == "retain"
    r = _invoke(tmp_path, "build-ninmed", "--source-dir", str(src), "--output", str(src / "tf"))
    assert r.returncode != 0
    assert not (src / "tf" / "otype.tf").exists()
