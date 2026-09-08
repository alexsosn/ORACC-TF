from __future__ import annotations

from io import BytesIO
import json
import math
from pathlib import Path
import struct
import zipfile

import pytest

from oracc_tf.archive_security import (
    ArchiveLimits,
    ArchiveResourceLimitError,
    ArchiveStructureError,
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


def forge_eocd_member_count(payload: bytes, count: int) -> bytes:
    data = bytearray(payload)
    position = data.rfind(b"PK\x05\x06")
    assert position >= 0
    struct.pack_into("<H", data, position + 8, count)
    struct.pack_into("<H", data, position + 10, count)
    return bytes(data)


def add_hybrid_zip64_records(payload: bytes) -> bytes:
    """Insert valid ZIP64 metadata while leaving classic EOCD fields non-sentinel."""
    position = payload.rfind(b"PK\x05\x06")
    assert position >= 0
    (
        signature,
        disk_number,
        central_disk,
        entries_on_disk,
        entries_total,
        central_size,
        central_offset,
        comment_length,
    ) = struct.unpack_from("<4s4H2LH", payload, position)
    assert signature == b"PK\x05\x06"
    assert disk_number == central_disk == 0
    assert entries_on_disk == entries_total
    assert comment_length == 0

    zip64_eocd = struct.pack(
        "<4sQ2H2L4Q",
        b"PK\x06\x06",
        44,
        45,
        45,
        0,
        0,
        entries_total,
        entries_total,
        central_size,
        central_offset,
    )
    locator = struct.pack(
        "<4sLQL",
        b"PK\x06\x07",
        0,
        position,
        1,
    )
    return payload[:position] + zip64_eocd + locator + payload[position:]


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


@pytest.mark.parametrize(
    "member",
    [
        "safe/project/CON",
        "safe/project/con.txt",
        "safe/project/COM1.log",
        "safe/project/COM¹",
        "safe/project/LPT².txt",
        "safe/project/com³.log",
        "safe/project/trailing-dot.",
        "safe/project/trailing-space ",
        "safe/project/data:alternate",
        "safe/project/bad?.json",
    ],
)
def test_preflight_rejects_windows_special_path_components(
    tmp_path: Path, member: str
) -> None:
    """Portable extraction must reject Windows device/alias/ADS path semantics."""
    path = write_archive(tmp_path, archive_with([(member, b"x")]))

    with pytest.raises(ArchiveStructureError):
        preflight_archive(path, limits())


def test_member_limit_is_checked_before_zipfile_materializes_central_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The member-count ceiling must protect the central-directory parse itself."""
    path = write_archive(
        tmp_path,
        archive_with(
            [
                ("safe/project/a.json", b"a"),
                ("safe/project/b.json", b"b"),
            ]
        ),
    )

    def forbidden_zipfile(*args: object, **kwargs: object) -> object:
        raise AssertionError("ZipFile materialized before member-count precheck")

    monkeypatch.setattr("oracc_tf.archive_security.zipfile.ZipFile", forbidden_zipfile)

    with pytest.raises(ArchiveResourceLimitError):
        preflight_archive(path, limits(max_members=1))


def test_member_limit_does_not_trust_forged_eocd_entry_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A forged low EOCD count must not bypass the pre-allocation member ceiling."""
    payload = archive_with(
        [
            ("safe/project/a.json", b"a"),
            ("safe/project/b.json", b"b"),
        ]
    )
    path = write_archive(tmp_path, forge_eocd_member_count(payload, 1))

    def forbidden_zipfile(*args: object, **kwargs: object) -> object:
        raise AssertionError("ZipFile materialized after forged EOCD count")

    monkeypatch.setattr("oracc_tf.archive_security.zipfile.ZipFile", forbidden_zipfile)

    with pytest.raises(ArchiveResourceLimitError):
        preflight_archive(path, limits(max_members=1))


def test_hybrid_zip64_is_rejected_before_zipfile_materialization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ZIP64 locator/EOCD metadata is a stop condition even with ordinary classic EOCD fields."""
    path = write_archive(tmp_path, add_hybrid_zip64_records(archive_with([])))

    def forbidden_zipfile(*args: object, **kwargs: object) -> object:
        raise AssertionError("ZipFile materialized before hybrid ZIP64 rejection")

    monkeypatch.setattr("oracc_tf.archive_security.zipfile.ZipFile", forbidden_zipfile)

    with pytest.raises(ArchiveStructureError):
        preflight_archive(path, limits())
