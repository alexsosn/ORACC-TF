from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import importlib
import json
from pathlib import Path
import stat
import struct
import unicodedata
import zipfile

import pytest


def api():
    return importlib.import_module("oracc_tf.archive_security")


def limits(module, **overrides):
    values = {
        "max_download_bytes": 1_000_000,
        "max_members": 100,
        "max_member_uncompressed_bytes": 100_000,
        "max_total_uncompressed_bytes": 500_000,
        "max_compression_ratio": 100.0,
    }
    values.update(overrides)
    return module.ArchiveLimits(**values)


def make_zip(
    entries: list[tuple[str | zipfile.ZipInfo, bytes]],
    *,
    compression: int = zipfile.ZIP_DEFLATED,
) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=compression) as archive:
        for name, payload in entries:
            archive.writestr(name, payload)
    return buffer.getvalue()


def oracc_zip(
    project: str = "aemw/alalakh/idrimi",
    *,
    text_payload: bytes = b'{"type":"cdl"}',
    compression: int = zipfile.ZIP_DEFLATED,
) -> bytes:
    metadata = {
        "type": "metadata",
        "project": project,
        "config": {"pathname": project},
    }
    return make_zip(
        [
            (f"{project}/metadata.json", json.dumps(metadata).encode("utf-8")),
            (f"{project}/corpusjson/P000001.json", text_payload),
        ],
        compression=compression,
    )


def write_payload(tmp_path: Path, payload: bytes, name: str = "source.zip") -> Path:
    path = tmp_path / name
    path.write_bytes(payload)
    return path


def patch_encrypted_flag(payload: bytes) -> bytes:
    data = bytearray(payload)
    local = data.find(b"PK\x03\x04")
    central = data.find(b"PK\x01\x02")
    assert local >= 0 and central >= 0
    local_flags = struct.unpack_from("<H", data, local + 6)[0] | 0x1
    central_flags = struct.unpack_from("<H", data, central + 8)[0] | 0x1
    struct.pack_into("<H", data, local + 6, local_flags)
    struct.pack_into("<H", data, central + 8, central_flags)
    return bytes(data)


def tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_stream_to_temp_hashes_exact_chunks_and_records_length(tmp_path: Path) -> None:
    module = api()
    chunks = [b"PK", b"\x03\x04", b"payload", b"-tail"]
    expected = b"".join(chunks)

    result = module.stream_to_temp(chunks, temp_dir=tmp_path, limits=limits(module))

    assert result.path.read_bytes() == expected
    assert result.bytes == len(expected)
    assert result.sha256 == sha256(expected).hexdigest()


def test_stream_to_temp_enforces_cap_and_cleans_partial_file(tmp_path: Path) -> None:
    module = api()
    before = set(tmp_path.iterdir())

    with pytest.raises(module.ArchiveResourceLimitError):
        module.stream_to_temp(
            [b"12345", b"67890"],
            temp_dir=tmp_path,
            limits=limits(module, max_download_bytes=8),
        )

    assert set(tmp_path.iterdir()) == before


def test_stream_to_temp_rejects_non_bytes_and_cleans_partial_file(tmp_path: Path) -> None:
    module = api()
    before = set(tmp_path.iterdir())

    with pytest.raises(module.ArchiveDownloadError):
        module.stream_to_temp(
            [b"prefix", "not-bytes"],  # type: ignore[list-item]
            temp_dir=tmp_path,
            limits=limits(module),
        )

    assert set(tmp_path.iterdir()) == before


def test_two_fetch_accepts_only_matching_independent_streams(tmp_path: Path) -> None:
    module = api()
    payload = oracc_zip()
    calls = 0

    def fetch_once():
        nonlocal calls
        calls += 1
        return [payload[:17], payload[17:]]

    result = module.acquire_unseen(fetch_once, temp_dir=tmp_path, limits=limits(module))

    assert calls == 2
    assert result.bytes == len(payload)
    assert result.sha256 == sha256(payload).hexdigest()
    assert result.path.read_bytes() == payload
    assert [p for p in tmp_path.iterdir() if p.is_file()] == [result.path]


@pytest.mark.parametrize(
    ("first", "second"),
    [
        (b"PK\x03\x04AAAA", b"PK\x03\x04AAAA-more"),
        (b"PK\x03\x04AAAA", b"PK\x03\x04BBBB"),
    ],
)
def test_two_fetch_mismatch_is_blocking_and_cleans_both_copies(
    tmp_path: Path, first: bytes, second: bytes
) -> None:
    module = api()
    responses = iter(([first], [second]))

    with pytest.raises(module.ArchiveVerificationMismatch):
        module.acquire_unseen(
            lambda: next(responses), temp_dir=tmp_path, limits=limits(module)
        )

    assert list(tmp_path.iterdir()) == []


def test_second_fetch_failure_cleans_first_copy(tmp_path: Path) -> None:
    module = api()
    payload = oracc_zip()
    calls = 0

    def fetch_once():
        nonlocal calls
        calls += 1
        if calls == 1:
            return [payload]

        def broken():
            yield b"partial"
            raise RuntimeError("network interrupted")

        return broken()

    with pytest.raises(RuntimeError, match="network interrupted"):
        module.acquire_unseen(fetch_once, temp_dir=tmp_path, limits=limits(module))

    assert calls == 2
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("payload", [b"404\n", b"PK\x03\x04truncated"])
def test_preflight_rejects_non_zip_or_truncated_bytes(tmp_path: Path, payload: bytes) -> None:
    module = api()
    path = write_payload(tmp_path, payload)

    with pytest.raises(module.ArchiveStructureError):
        module.preflight_archive(path, limits(module))


@pytest.mark.parametrize(
    "member",
    [
        "../escape.json",
        "/absolute.json",
        "C:/drive.json",
        "project\\windows.json",
        "project/./dot.json",
        "project//empty.json",
    ],
)
def test_preflight_rejects_unsafe_member_paths(tmp_path: Path, member: str) -> None:
    module = api()
    payload = make_zip([(member, b"x")])
    path = write_payload(tmp_path, payload)

    with pytest.raises(module.ArchiveStructureError):
        module.preflight_archive(path, limits(module))


@pytest.mark.parametrize("file_type", [stat.S_IFLNK, stat.S_IFIFO, stat.S_IFCHR])
def test_preflight_rejects_symlink_and_special_file_entries(
    tmp_path: Path, file_type: int
) -> None:
    module = api()
    info = zipfile.ZipInfo("project/member")
    info.create_system = 3
    info.external_attr = (file_type | 0o777) << 16
    path = write_payload(tmp_path, make_zip([(info, b"target")]))

    with pytest.raises(module.ArchiveStructureError):
        module.preflight_archive(path, limits(module))


def test_preflight_rejects_encrypted_entries_before_reading_them(tmp_path: Path) -> None:
    module = api()
    payload = make_zip([("project/secret.json", b"secret")], compression=zipfile.ZIP_STORED)
    path = write_payload(tmp_path, patch_encrypted_flag(payload))

    with pytest.raises(module.ArchiveStructureError):
        module.preflight_archive(path, limits(module))


def test_preflight_rejects_literal_duplicate_members(tmp_path: Path) -> None:
    module = api()
    with pytest.warns(UserWarning, match="Duplicate name"):
        payload = make_zip(
            [("project/x.json", b"one"), ("project/x.json", b"two")]
        )
    path = write_payload(tmp_path, payload)

    with pytest.raises(module.ArchiveStructureError):
        module.preflight_archive(path, limits(module))


def test_preflight_rejects_non_nfc_and_casefold_aliases(tmp_path: Path) -> None:
    module = api()
    decomposed = "project/cafe\u0301.json"
    assert decomposed != unicodedata.normalize("NFC", decomposed)
    non_nfc = write_payload(tmp_path, make_zip([(decomposed, b"x")]), "nfc.zip")
    case_alias = write_payload(
        tmp_path,
        make_zip([("project/A.json", b"one"), ("project/a.json", b"two")]),
        "case.zip",
    )

    with pytest.raises(module.ArchiveStructureError):
        module.preflight_archive(non_nfc, limits(module))
    with pytest.raises(module.ArchiveStructureError):
        module.preflight_archive(case_alias, limits(module))


def test_preflight_rejects_file_directory_prefix_collision(tmp_path: Path) -> None:
    module = api()
    path = write_payload(
        tmp_path,
        make_zip([("project/node", b"file"), ("project/node/child.json", b"child")]),
    )

    with pytest.raises(module.ArchiveStructureError):
        module.preflight_archive(path, limits(module))


def test_preflight_rejects_unsupported_compression(tmp_path: Path) -> None:
    module = api()
    path = write_payload(
        tmp_path,
        make_zip([("project/data.json", b"{}")], compression=zipfile.ZIP_BZIP2),
    )

    with pytest.raises(module.ArchiveStructureError):
        module.preflight_archive(path, limits(module))


def test_preflight_enforces_member_count_size_total_and_ratio_limits(tmp_path: Path) -> None:
    module = api()
    two_members = write_payload(
        tmp_path,
        make_zip([("p/a", b"1"), ("p/b", b"2")]),
        "members.zip",
    )
    big_member = write_payload(tmp_path, make_zip([("p/a", b"x" * 20)]), "member.zip")
    big_total = write_payload(
        tmp_path,
        make_zip([("p/a", b"x" * 8), ("p/b", b"y" * 8)]),
        "total.zip",
    )
    high_ratio = write_payload(
        tmp_path,
        make_zip([("p/a", b"A" * 10_000)]),
        "ratio.zip",
    )

    with pytest.raises(module.ArchiveResourceLimitError):
        module.preflight_archive(two_members, limits(module, max_members=1))
    with pytest.raises(module.ArchiveResourceLimitError):
        module.preflight_archive(big_member, limits(module, max_member_uncompressed_bytes=10))
    with pytest.raises(module.ArchiveResourceLimitError):
        module.preflight_archive(big_total, limits(module, max_total_uncompressed_bytes=10))
    with pytest.raises(module.ArchiveResourceLimitError):
        module.preflight_archive(high_ratio, limits(module, max_compression_ratio=5.0))


def test_preflight_derives_legitimate_three_level_project_from_archive_structure(
    tmp_path: Path,
) -> None:
    module = api()
    path = write_payload(tmp_path, oracc_zip(), "misleading-flat-name.zip")

    layout = module.preflight_archive(path, limits(module))

    assert layout.project_roots == ("aemw/alalakh/idrimi",)
    assert "aemw/alalakh/idrimi/metadata.json" in layout.members
    assert "aemw/alalakh/idrimi/corpusjson/P000001.json" in layout.members


def test_preflight_rejects_metadata_pathname_or_project_mismatch(tmp_path: Path) -> None:
    module = api()
    root = "aemw/alalakh/idrimi"
    bad_pathname = {
        "type": "metadata",
        "project": root,
        "config": {"pathname": "aemw/alalakh"},
    }
    bad_project = {
        "type": "metadata",
        "project": "other/project",
        "config": {"pathname": root},
    }
    first = write_payload(
        tmp_path,
        make_zip([(f"{root}/metadata.json", json.dumps(bad_pathname).encode())]),
        "pathname.zip",
    )
    second = write_payload(
        tmp_path,
        make_zip([(f"{root}/metadata.json", json.dumps(bad_project).encode())]),
        "project.zip",
    )

    with pytest.raises(module.ArchiveStructureError):
        module.preflight_archive(first, limits(module))
    with pytest.raises(module.ArchiveStructureError):
        module.preflight_archive(second, limits(module))


def test_extract_requires_absent_destination_and_preserves_existing_tree(tmp_path: Path) -> None:
    module = api()
    archive = write_payload(tmp_path, oracc_zip())
    destination = tmp_path / "snapshot"
    destination.mkdir()
    sentinel = destination / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")

    with pytest.raises(module.ArchiveExtractionError):
        module.extract_archive(archive, destination, limits(module))

    assert sentinel.read_text(encoding="utf-8") == "keep"


def test_mid_extraction_crc_failure_leaves_no_destination_or_staging_tree(tmp_path: Path) -> None:
    module = api()
    marker = b"PAYLOAD-CONTENT-UNIQUE"
    payload = bytearray(oracc_zip(text_payload=marker, compression=zipfile.ZIP_STORED))
    offset = payload.find(marker)
    assert offset >= 0
    payload[offset] ^= 0x01
    archive = write_payload(tmp_path, bytes(payload))
    destination = tmp_path / "snapshot"
    before = set(tmp_path.iterdir())

    with pytest.raises(module.ArchiveExtractionError):
        module.extract_archive(archive, destination, limits(module))

    assert not destination.exists()
    assert set(tmp_path.iterdir()) == before


def test_identical_bytes_extract_to_identical_trees(tmp_path: Path) -> None:
    module = api()
    archive = write_payload(tmp_path, oracc_zip())
    first = tmp_path / "first"
    second = tmp_path / "second"

    first_layout = module.extract_archive(archive, first, limits(module))
    second_layout = module.extract_archive(archive, second, limits(module))

    assert first_layout == second_layout
    assert tree_bytes(first) == tree_bytes(second)
    assert first_layout.project_roots == ("aemw/alalakh/idrimi",)
