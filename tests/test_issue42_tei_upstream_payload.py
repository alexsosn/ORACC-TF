"""ISSUE-42 RED payload-type contract; safe extraction remains P-002.PH3-owned."""

from __future__ import annotations

from io import BytesIO
import hashlib
import importlib
import zipfile

import pytest


LISTING = "https://oracc.example/riao/downloads/"


def api():
    return importlib.import_module("oracc_tf.tei_upstream")


def candidate(module):
    return module.parse_download_listing(
        '<a href="riao-teiCorpus-20241202.zip">TEI</a>',
        LISTING,
    )[0]


def valid_zip_bytes() -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("riao/tei/Q000001.xml", "<TEI/>")
    return buffer.getvalue()


def test_soft_404_body_is_not_accepted_as_verified_tei_source() -> None:
    module = api()

    with pytest.raises(module.TeiDiscoveryError):
        module.verify_candidate_bytes(candidate(module), b"404\n")


def test_soft_404_prefix_cannot_hide_a_valid_zip_tail() -> None:
    module = api()

    with pytest.raises(module.TeiDiscoveryError):
        module.verify_candidate_bytes(candidate(module), b"404\n" + valid_zip_bytes())


def test_verified_payload_records_own_sha256_and_size_without_extracting() -> None:
    module = api()
    payload = valid_zip_bytes()

    verified = module.verify_candidate_bytes(candidate(module), payload)

    assert verified.sha256 == hashlib.sha256(payload).hexdigest()
    assert verified.bytes == len(payload)


def test_payload_type_check_does_not_read_or_decompress_members(monkeypatch) -> None:
    module = api()
    payload = valid_zip_bytes()

    def forbidden_open(*args, **kwargs):
        raise AssertionError("ISSUE-42 must not read/decompress ZIP members; PH3 owns that")

    monkeypatch.setattr(zipfile.ZipFile, "open", forbidden_open)

    verified = module.verify_candidate_bytes(candidate(module), payload)

    assert verified.sha256 == hashlib.sha256(payload).hexdigest()


def test_verified_candidate_rejects_non_candidate_identity() -> None:
    module = api()

    with pytest.raises(module.TeiDiscoveryError):
        module.VerifiedTeiCandidate(candidate=object(), sha256="a" * 64, bytes=1)


@pytest.mark.parametrize(
    ("sha256", "size"),
    [
        ("not-a-digest", 1),
        ("a" * 64, 0),
        ("a" * 64, -1),
        ("a" * 64, True),
    ],
)
def test_verified_candidate_rejects_invalid_verification_metadata(
    sha256: str, size: int
) -> None:
    module = api()

    with pytest.raises(module.TeiDiscoveryError):
        module.VerifiedTeiCandidate(
            candidate=candidate(module),
            sha256=sha256,
            bytes=size,
        )
