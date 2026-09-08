from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import zipfile

import pytest

from oracc_tf.archive_security import (
    ArchiveLimits,
    ArchiveResourceLimitError,
    preflight_archive,
)


def limits(**overrides: object) -> ArchiveLimits:
    values: dict[str, object] = {
        "max_download_bytes": 1_000_000,
        "max_members": 100,
        "max_member_uncompressed_bytes": 100_000,
        "max_total_uncompressed_bytes": 500_000,
        "max_compression_ratio": 100.0,
    }
    values.update(overrides)
    return ArchiveLimits(**values)  # type: ignore[arg-type]


def valid_archive() -> bytes:
    root = "safe/project"
    metadata = {
        "type": "metadata",
        "project": root,
        "config": {"pathname": root},
    }
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{root}/metadata.json", json.dumps(metadata).encode("utf-8"))
    return buffer.getvalue()


def test_preflight_applies_archive_byte_ceiling_before_zipfile_materialization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Direct/pinned preflight must honor the same archive-byte policy as downloads."""
    payload = valid_archive()
    path = tmp_path / "source.zip"
    path.write_bytes(payload)

    def forbidden_zipfile(*args: object, **kwargs: object) -> object:
        raise AssertionError("ZipFile materialized before archive-byte ceiling check")

    monkeypatch.setattr("oracc_tf.archive_security.zipfile.ZipFile", forbidden_zipfile)

    with pytest.raises(ArchiveResourceLimitError):
        preflight_archive(path, limits(max_download_bytes=len(payload) - 1))


def test_metadata_preflight_never_uses_unbounded_zip_member_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Metadata inspection must bound each decompression call, not call read() to EOF."""
    path = tmp_path / "source.zip"
    path.write_bytes(valid_archive())
    original_read = zipfile.ZipExtFile.read

    def bounded_only(self: zipfile.ZipExtFile, n: int = -1) -> bytes:
        if n is None or n < 0:
            raise AssertionError("unbounded ZipExtFile.read during metadata preflight")
        return original_read(self, n)

    monkeypatch.setattr(zipfile.ZipExtFile, "read", bounded_only)

    preflight_archive(path, limits())
