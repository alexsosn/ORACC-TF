"""RED-first checks for the minimal independently downloadable 1.0 archive."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from zipfile import ZipFile

import pytest

from oracc_tf import release_archive


DATASET = "assyrian-royal-inscriptions"
COMMIT = "a" * 40
SOURCE = "sha256:" + "b" * 64


def _staged_candidate(tmp_path: Path) -> Path:
    stage = tmp_path / "stage"
    (stage / "tf" / "0.4.0").mkdir(parents=True)
    (stage / "tf" / "0.4.0" / "otype.tf").write_text("@node\n", encoding="utf-8")
    (stage / "tf" / "0.4.0" / "oslots.tf").write_text("@edge\n", encoding="utf-8")
    (stage / "app").mkdir()
    (stage / "app" / "config.yaml").write_text("apiVersion: 3\n", encoding="utf-8")
    ref = stage / "docs" / "reference"
    ref.mkdir(parents=True)
    (stage / "docs" / "index.md").write_text("# Researcher manual\n", encoding="utf-8")
    for name in release_archive.REQUIRED_DOCUMENTS:
        (ref / name).write_text(f"# {name}\n", encoding="utf-8")
    (stage / "docs" / "CITATION.cff").write_text(
        "cff-version: 1.2.0\n", encoding="utf-8"
    )
    (stage / "docs" / "LICENSE_SCOPE.md").write_text(
        "# Upstream source rights\n", encoding="utf-8"
    )
    (stage / "README.md").write_text("# Standalone release\n", encoding="utf-8")
    (stage / "manifest.json").write_text(
        json.dumps(
            {
                "dataset": DATASET,
                "release_id": "1.0.0",
                "tf_version": "0.4.0",
                "tf_root": "tf/0.4.0",
                "builder_commit": COMMIT,
                "source_state": SOURCE,
                "support_roots": {"app": {}, "docs": {}},
            }
        ),
        encoding="utf-8",
    )
    return stage


def test_release_archive_from_staged_candidate_is_complete_and_checksummed(
    tmp_path: Path,
) -> None:
    stage = _staged_candidate(tmp_path)
    archive, checksum = release_archive.package_release(stage, tmp_path / "output")
    assert archive.name == DATASET + "-1.0.0.zip"
    assert checksum.name == archive.name + ".sha256"
    assert checksum.read_text(encoding="utf-8") == (
        f"{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n"
    )
    with ZipFile(archive) as zf:
        names = set(zf.namelist())
        assert "manifest.json" in names and "README.md" in names
        assert "tf/0.4.0/otype.tf" in names
        assert "tf/0.4.0/oslots.tf" in names
        assert "app/config.yaml" in names
        assert "docs/reference/quick-start.md" in names
        assert "docs/reference/citation.md" in names
        assert "docs/CITATION.cff" in names
        assert "docs/LICENSE_SCOPE.md" in names
        assert not any(n.startswith(("data/", "programs/", "docs/task-state/")) for n in names)
        assert zf.read("manifest.json") == (stage / "manifest.json").read_bytes()


@pytest.mark.parametrize(
    "missing",
    [
        "tf/0.4.0/otype.tf",
        "app/config.yaml",
        "docs/reference/quick-start.md",
        "docs/reference/known-issues.md",
        "docs/CITATION.cff",
        "docs/LICENSE_SCOPE.md",
    ],
)
def test_release_refuses_missing_reader_payload(tmp_path: Path, missing: str) -> None:
    stage = _staged_candidate(tmp_path)
    (stage / missing).unlink()
    with pytest.raises(release_archive.ReleasePackageError, match="missing"):
        release_archive.package_release(stage, tmp_path / "out")


def test_release_rejects_untracked_builder_data_and_symlinks(tmp_path: Path) -> None:
    stage = _staged_candidate(tmp_path)
    (stage / "data").mkdir()
    (stage / "data" / "source.json").write_text("{}", encoding="utf-8")
    with pytest.raises(release_archive.ReleasePackageError, match="forbidden"):
        release_archive.package_release(stage, tmp_path / "out")
    (stage / "data" / "source.json").unlink()
    (stage / "data").rmdir()
    (stage / "docs" / "reference" / "bad.md").symlink_to(
        stage / "README.md"
    )
    with pytest.raises(release_archive.ReleasePackageError, match="symlink"):
        release_archive.package_release(stage, tmp_path / "out")


def test_release_detects_inconsistent_manifest_and_avoids_clobbering(
    tmp_path: Path,
) -> None:
    stage = _staged_candidate(tmp_path)
    manifest = json.loads((stage / "manifest.json").read_text(encoding="utf-8"))
    manifest["tf_root"] = "tf/old"
    (stage / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(release_archive.ReleasePackageError, match="tf_root"):
        release_archive.package_release(stage, tmp_path / "out")
    manifest["tf_root"] = "tf/0.4.0"
    (stage / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    release_archive.package_release(stage, tmp_path / "out")
    with pytest.raises(release_archive.ReleasePackageError, match="exists"):
        release_archive.package_release(stage, tmp_path / "out")


def test_release_refuses_unowned_files_even_if_not_named_builder_data(
    tmp_path: Path,
) -> None:
    stage = _staged_candidate(tmp_path)
    (stage / ".env").write_text("SHOULD_NEVER_SHIP=secret\n", encoding="utf-8")
    with pytest.raises(release_archive.ReleasePackageError, match="forbidden"):
        release_archive.package_release(stage, tmp_path / "out")


def test_release_refuses_unowned_hidden_file_inside_allowed_manual_root(
    tmp_path: Path,
) -> None:
    stage = _staged_candidate(tmp_path)
    (stage / "docs" / ".env").write_text("TOKEN=do-not-publish\n", encoding="utf-8")
    with pytest.raises(release_archive.ReleasePackageError, match="hidden"):
        release_archive.package_release(stage, tmp_path / "out")


def test_archive_bytes_do_not_depend_on_source_file_mtimes(tmp_path: Path) -> None:
    stage = _staged_candidate(tmp_path)
    a, _ = release_archive.package_release(stage, tmp_path / "out1")
    for path in stage.rglob("*"):
        if path.is_file():
            os.utime(path, (1_600_000_000, 1_600_000_000))
    b, _ = release_archive.package_release(stage, tmp_path / "out2")
    assert a.read_bytes() == b.read_bytes()
