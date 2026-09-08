from __future__ import annotations

from io import BytesIO
import json
import math
from pathlib import Path
import zipfile

import pytest

from oracc_tf.archive_security import (
    ArchiveLimits,
    ArchiveResourceLimitError,
    ArchiveStructureError,
    preflight_archive,
)


def limits() -> ArchiveLimits:
    return ArchiveLimits(
        max_download_bytes=1_000_000,
        max_members=100,
        max_member_uncompressed_bytes=100_000,
        max_total_uncompressed_bytes=500_000,
        max_compression_ratio=100.0,
    )


def archive_with(extra_entries: list[tuple[str, bytes]]) -> bytes:
    root = "safe/project"
    metadata = {
        "type": "metadata",
        "project": root,
        "config": {"pathname": root},
    }
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{root}/metadata.json", json.dumps(metadata).encode("utf-8"))
        for name, payload in extra_entries:
            archive.writestr(name, payload)
    return buffer.getvalue()


def write_archive(tmp_path: Path, payload: bytes) -> Path:
    path = tmp_path / "source.zip"
    path.write_bytes(payload)
    return path


@pytest.mark.parametrize("ratio", [math.nan, math.inf, -math.inf])
def test_archive_limits_reject_non_finite_compression_ratio(ratio: float) -> None:
    """A non-finite ceiling must not disable compression-ratio enforcement."""
    with pytest.raises(ArchiveResourceLimitError):
        ArchiveLimits(
            max_download_bytes=1_000_000,
            max_members=100,
            max_member_uncompressed_bytes=100_000,
            max_total_uncompressed_bytes=500_000,
            max_compression_ratio=ratio,
        )


def test_preflight_rejects_casefold_aliases_in_ancestor_directories(tmp_path: Path) -> None:
    """Distinct child names must not hide an alias collision in their parents."""
    path = write_archive(
        tmp_path,
        archive_with(
            [
                ("AliasRoot/a.json", b"a"),
                ("aliasroot/b.json", b"b"),
            ]
        ),
    )

    with pytest.raises(ArchiveStructureError):
        preflight_archive(path, limits())


def test_preflight_rejects_casefold_file_directory_prefix_collision(tmp_path: Path) -> None:
    """A file and a differently-cased directory alias cannot coexist safely."""
    path = write_archive(
        tmp_path,
        archive_with(
            [
                ("AliasRoot", b"file"),
                ("aliasroot/child.json", b"child"),
            ]
        ),
    )

    with pytest.raises(ArchiveStructureError):
        preflight_archive(path, limits())
