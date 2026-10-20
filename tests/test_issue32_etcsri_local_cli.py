"""Researcher-facing ETCSRI converter CLI: source-grounded RED and E2E smoke.

No ORACC data goes into the installed wheel: callers supply actual corpusjson.
Tests use a pinned real source document, not a hand-constructed one-word edition.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import subprocess
import sys

from tf.fabric import Fabric
from oracc_tf import paths


WITNESS = paths.DATA / "etcsri" / "corpusjson" / "Q000935.json"
SOURCE_GIT_BLOB = "a2eef2a0337d276191fbda85a4269948fb00f9c3"


def _source(tmp_path: Path) -> Path:
    raw = WITNESS.read_bytes()
    preimage = f"blob {len(raw)}".encode("ascii") + bytes([0]) + raw
    assert hashlib.sha1(preimage).hexdigest() == SOURCE_GIT_BLOB
    target = tmp_path / "input" / "corpusjson"
    target.mkdir(parents=True)
    shutil.copyfile(WITNESS, target / WITNESS.name)
    return target


def _invoke(*arguments: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "oracc_tf", *arguments],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def test_installed_module_exposes_real_etcsri_build_help(tmp_path: Path) -> None:
    result = _invoke("build-etcsri", "--help", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert "--source-dir" in result.stdout
    assert "--output" in result.stdout
    assert "--text-id" in result.stdout


def test_real_etcsri_source_to_loadable_tf_via_user_cli(tmp_path: Path) -> None:
    source = _source(tmp_path)
    output = tmp_path / "tf"
    result = _invoke(
        "build-etcsri", "--source-dir", str(source),
        "--output", str(output), "--text-id", "Q000935",
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert (output / "otype.tf").exists()
    assert (output / "morph.tf").exists()
    assert "Q000935" in result.stdout
    assert "7" in result.stdout
    tf = Fabric(locations=str(output), silent="deep")
    assert tf.loadAll(silent="deep")
    api = tf.api
    assert api is not None
    words = api.F.otype.s("word")
    assert len(words) == 7
    assert {api.F.document_key.v(n) for n in words} == {"etcsri:Q000935"}
    assert sum(bool(api.F.morph.v(n)) for n in words) == 7


def test_missing_requested_edition_fails_without_writing_tf(tmp_path: Path) -> None:
    source = _source(tmp_path)
    output = tmp_path / "output"
    result = _invoke(
        "build-etcsri", "--source-dir", str(source),
        "--output", str(output), "--text-id", "Q999999", cwd=tmp_path,
    )
    assert result.returncode != 0
    assert "Q999999" in result.stderr
    assert not (output / "otype.tf").exists()


def test_missing_source_and_nonempty_output_fail_closed(tmp_path: Path) -> None:
    source = _source(tmp_path)
    result = _invoke(
        "build-etcsri", "--source-dir", str(tmp_path / "no-source"),
        "--output", str(tmp_path / "other"), cwd=tmp_path,
    )
    assert result.returncode != 0
    output = tmp_path / "output"
    output.mkdir()
    (output / "user-data.txt").write_text("keep", encoding="utf-8")
    result = _invoke(
        "build-etcsri", "--source-dir", str(source),
        "--output", str(output), cwd=tmp_path,
    )
    assert result.returncode != 0
    assert (output / "user-data.txt").read_text(encoding="utf-8") == "keep"
    assert not (output / "otype.tf").exists()


def test_output_under_source_directory_is_rejected(tmp_path: Path) -> None:
    source = _source(tmp_path)
    result = _invoke(
        "build-etcsri", "--source-dir", str(source),
        "--output", str(source / "converted"), cwd=tmp_path,
    )
    assert result.returncode != 0
    assert not (source / "converted" / "otype.tf").exists()
