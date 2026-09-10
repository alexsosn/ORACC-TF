from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import struct
import zipfile

import pytest

from oracc_tf.archive_security import (
    ArchiveLimits,
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


def corrupt_central_filename_utf8(payload: bytes) -> bytes:
    """Set UTF-8 on a central-directory entry and inject an invalid byte."""
    data = bytearray(payload)
    central = data.find(b"PK\x01\x02")
    assert central >= 0

    flags = struct.unpack_from("<H", data, central + 8)[0]
    struct.pack_into("<H", data, central + 8, flags | 0x0800)

    filename_length = struct.unpack_from("<H", data, central + 28)[0]
    assert filename_length > 0
    filename_start = central + 46
    data[filename_start] = 0xFF
    return bytes(data)


def test_malformed_utf8_central_filename_is_typed_structure_failure(tmp_path: Path) -> None:
    """Malformed remote ZIP names must not leak raw UnicodeDecodeError."""
    path = tmp_path / "source.zip"
    path.write_bytes(corrupt_central_filename_utf8(valid_archive()))

    with pytest.raises(ArchiveStructureError):
        preflight_archive(path, limits())
