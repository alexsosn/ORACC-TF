from __future__ import annotations

from io import BytesIO
import importlib
import json
from pathlib import Path
import zipfile

import pytest


CRC_COLLISION_A = b"Z\xfc\tv\xd0\xff{\x06\xae\x84\xdb\xbb"
CRC_COLLISION_B = b'\x11\t\x0f&"\xba\xbd\xf5\xd4!\n\xf4'


def api():
    return importlib.import_module("oracc_tf.archive_security")


def limits(module):
    return module.ArchiveLimits(
        max_download_bytes=1_000_000,
        max_members=100,
        max_member_uncompressed_bytes=100_000,
        max_total_uncompressed_bytes=500_000,
        max_compression_ratio=100.0,
    )


def oracc_zip(payload: bytes, *, member_name: str = "P000001.json") -> bytes:
    root = "safe/project"
    metadata = {
        "type": "metadata",
        "project": root,
        "config": {"pathname": root},
    }
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr(
            f"{root}/metadata.json",
            json.dumps(metadata, separators=(",", ":")).encode("utf-8"),
        )
        archive.writestr(f"{root}/corpusjson/{member_name}", payload)
    return buffer.getvalue()


def test_preflight_rejects_raw_filename_truncated_at_nul(tmp_path: Path) -> None:
    """zipfile's NUL truncation must not turn an unsafe raw name into a safe path."""
    marker = b"P000001Xjson"
    replacement = b"P000001\x00json"
    payload = oracc_zip(b"{}", member_name=marker.decode("ascii"))
    assert payload.count(marker) == 2  # local header + central directory
    payload = payload.replace(marker, replacement)
    path = tmp_path / "nul-name.zip"
    path.write_bytes(payload)

    with pytest.raises(api().ArchiveStructureError):
        api().preflight_archive(path, limits(api()))


def test_extract_uses_preflighted_bytes_when_source_path_changes_after_preflight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reopening the caller path must not let different same-layout bytes reach output."""
    module = api()
    first = oracc_zip(CRC_COLLISION_A)
    second = oracc_zip(CRC_COLLISION_B)
    assert len(first) == len(second)
    assert first != second

    source = tmp_path / "source.zip"
    source.write_bytes(first)
    destination = tmp_path / "snapshot"
    original_inspect = module._inspect_archive

    def inspect_then_replace(inspected_path: Path | str, archive_limits):
        result = original_inspect(inspected_path, archive_limits)
        source.write_bytes(second)
        return result

    monkeypatch.setattr(module, "_inspect_archive", inspect_then_replace)

    module.extract_archive(source, destination, limits(module))

    assert destination.joinpath("safe/project/corpusjson/P000001.json").read_bytes() == CRC_COLLISION_A


def test_verified_extraction_rejects_tampered_two_fetch_result(tmp_path: Path) -> None:
    """The identity accepted by acquire_unseen must be re-bound to extraction bytes."""
    module = api()
    first = oracc_zip(CRC_COLLISION_A)
    second = oracc_zip(CRC_COLLISION_B)
    assert len(first) == len(second)
    calls = 0

    def fetch_once():
        nonlocal calls
        calls += 1
        return [first]

    verified = module.acquire_unseen(fetch_once, temp_dir=tmp_path, limits=limits(module))
    assert calls == 2
    verified.path.write_bytes(second)
    before = set(tmp_path.iterdir())
    destination = tmp_path / "snapshot"

    with pytest.raises(module.ArchiveVerificationMismatch):
        module.extract_verified_archive(verified, destination, limits(module))

    assert not destination.exists()
    assert set(tmp_path.iterdir()) == before
