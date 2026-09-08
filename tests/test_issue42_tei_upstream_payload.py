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


def test_verified_payload_records_own_sha256_and_size_without_extracting() -> None:
    module = api()
    payload = valid_zip_bytes()

    verified = module.verify_candidate_bytes(candidate(module), payload)

    assert verified.sha256 == hashlib.sha256(payload).hexdigest()
    assert verified.bytes == len(payload)
