"""P-002 PH2 RED contracts for upstream discovery/change detection."""

from __future__ import annotations

from io import BytesIO
import hashlib
import importlib
from pathlib import Path
import zipfile

import pytest


INDEX = "http://oracc.museum.upenn.edu/json/"
SHA_A = "a" * 64
SHA_B = "b" * 64
EXPECTED_TRACKED = (
    "riao-ria1",
    "riao-ria2",
    "riao-ria3",
    "riao-ria4",
    "riao-ria5",
    "rinap-rinap1",
    "rinap-rinap2",
    "rinap-rinap3",
    "rinap-rinap4",
    "rinap-rinap5",
    "rinap-rinap5p1",
)


def api():
    return importlib.import_module("oracc_tf.upstream_discovery")


def archive_entry(module, name: str = "riao-ria1"):
    return module.parse_archive_inventory(
        f'<a href="{name}.zip">{name}</a>', INDEX
    )[0]


def fingerprint(
    module,
    *,
    name: str = "riao-ria1",
    sha256: str = SHA_A,
    size: int = 123,
    etag: str | None = '"etag-a"',
    last_modified: str | None = "Sat, 29 Apr 2023 09:57:38 GMT",
):
    return module.ArchiveFingerprint(
        name=name,
        sha256=sha256,
        bytes=size,
        etag=etag,
        last_modified=last_modified,
    )


def head(
    module,
    *,
    etag: str | None = '"etag-a"',
    length: int | None = 123,
    last_modified: str | None = "Sat, 29 Apr 2023 09:57:38 GMT",
):
    headers: dict[str, str] = {}
    if etag is not None:
        headers["eTaG"] = etag
    if length is not None:
        headers["content-LENGTH"] = str(length)
    if last_modified is not None:
        headers["Last-Modified"] = last_modified
    return module.head_from_response(200, headers)


def valid_zip_bytes() -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("riao/ria1/metadata.json", "{}")
    return buffer.getvalue()


def test_archive_and_project_inventories_keep_separate_semantics() -> None:
    module = api()
    archive_html = """
    <a href="rinap-rinap1.zip">rinap</a>
    <a href="riao-ria1.zip">riao</a>
    <a href="README.txt">ignore</a>
    """
    projects_json = """
    {"type":"projects","public":["rinap/rinap1","aemw/alalakh/idrimi","riao/ria1"]}
    """

    archives = module.parse_archive_inventory(archive_html, INDEX)
    projects = module.parse_project_inventory(projects_json)

    assert tuple(item.name for item in archives) == ("riao-ria1", "rinap-rinap1")
    assert archives[0].url == INDEX + "riao-ria1.zip"
    assert projects.public == (
        "aemw/alalakh/idrimi",
        "riao/ria1",
        "rinap/rinap1",
    )
    assert not hasattr(projects, "archives")


def test_archive_inventory_is_order_independent_and_duplicate_links_are_idempotent() -> None:
    module = api()
    html_a = """
    <a href="rinap-rinap1.zip">b</a>
    <a href="riao-ria1.zip">a</a>
    <a href="riao-ria1.zip">dup</a>
    """
    html_b = """
    <a href="riao-ria1.zip">a</a>
    <a href="rinap-rinap1.zip">b</a>
    """

    assert module.parse_archive_inventory(html_a, INDEX) == module.parse_archive_inventory(
        html_b, INDEX
    )


def test_project_inventory_rejects_wrong_type_and_duplicate_public_paths() -> None:
    module = api()

    with pytest.raises(module.UpstreamInventoryError):
        module.parse_project_inventory('{"type":"projectlist","public":[]}')
    with pytest.raises(module.UpstreamInventoryError):
        module.parse_project_inventory(
            '{"type":"projects","public":["riao/ria1","riao/ria1"]}'
        )


def test_current_datasets_select_only_active_json_archives_and_exclude_tei() -> None:
    module = api()
    repo_root = Path(__file__).resolve().parents[1]
    tracked = module.tracked_archives_from_datasets(
        (repo_root / "datasets.toml").read_text(encoding="utf-8")
    )

    assert tracked == EXPECTED_TRACKED
    assert "riao-teiCorpus" not in tracked


def test_active_inventory_entries_ignore_untracked_but_require_every_tracked_archive() -> None:
    module = api()
    html = "\n".join(
        f'<a href="{name}.zip">{name}</a>' for name in (*EXPECTED_TRACKED, "etcsri")
    )
    inventory = module.parse_archive_inventory(html, INDEX)

    active = module.active_inventory_entries(inventory, EXPECTED_TRACKED)

    assert tuple(item.name for item in active) == EXPECTED_TRACKED
    assert "etcsri" not in {item.name for item in active}

    with pytest.raises(module.UpstreamInventoryError):
        module.active_inventory_entries(inventory, (*EXPECTED_TRACKED, "missing-project"))


@pytest.mark.parametrize("status", [500, 502, 503, 599])
def test_server_failure_is_typed_unavailable_and_never_an_unchanged_observation(status: int) -> None:
    module = api()

    with pytest.raises(module.UpstreamUnavailable):
        module.head_from_response(status, {})


@pytest.mark.parametrize("status", [301, 302, 404])
def test_unresolved_redirect_or_client_error_is_protocol_failure(status: int) -> None:
    module = api()

    with pytest.raises(module.UpstreamProtocolError):
        module.head_from_response(status, {"Location": "https://example.invalid/"})


def test_head_headers_are_case_insensitive_and_matching_etag_length_avoids_download() -> None:
    module = api()
    current = head(module)

    decision = module.decide_probe(fingerprint(module), current)

    assert current.etag == '"etag-a"'
    assert current.content_length == 123
    assert decision.action == "unchanged"
    assert decision.requires_download is False


@pytest.mark.parametrize(
    ("locked_etag", "head_etag", "head_length"),
    [
        (None, None, 123),
        ('"etag-a"', None, 123),
        ('"etag-a"', '"etag-a"', None),
        ('"etag-a"', '"etag-b"', 123),
        ('"etag-a"', '"etag-a"', 124),
    ],
)
def test_missing_or_changed_validator_metadata_requires_download(
    locked_etag: str | None,
    head_etag: str | None,
    head_length: int | None,
) -> None:
    module = api()

    decision = module.decide_probe(
        fingerprint(module, etag=locked_etag),
        head(module, etag=head_etag, length=head_length),
    )

    assert decision.action == "download-required"
    assert decision.requires_download is True


@pytest.mark.parametrize("etag", ["", "   "])
def test_empty_or_whitespace_etag_never_authorizes_unchanged(etag: str) -> None:
    module = api()
    decision = module.decide_probe(
        fingerprint(module, etag=etag),
        head(module, etag=etag, length=123),
    )

    assert decision.action == "download-required"
    assert decision.requires_download is True


def test_missing_content_length_is_insufficient_not_zero_or_unchanged() -> None:
    module = api()
    current = module.head_from_response(200, {"ETag": '"etag-a"'})

    assert current.content_length is None
    assert module.decide_probe(fingerprint(module), current).requires_download is True


def test_invalid_content_length_fails_closed() -> None:
    module = api()

    with pytest.raises(module.UpstreamProtocolError):
        module.head_from_response(200, {"ETag": '"etag-a"', "Content-Length": "nope"})


def test_transient_retry_uses_exponential_backoff_then_succeeds() -> None:
    module = api()
    calls = 0
    slept: list[float] = []

    def operation():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise module.UpstreamUnavailable("temporary")
        return "ok"

    result = module.with_retries(operation, attempts=3, sleep=slept.append)

    assert result == "ok"
    assert calls == 3
    assert slept == [1.0, 2.0]


def test_retry_exhaustion_raises_and_protocol_failures_are_not_retried() -> None:
    module = api()
    transient_calls = 0
    slept: list[float] = []

    def unavailable():
        nonlocal transient_calls
        transient_calls += 1
        raise module.UpstreamUnavailable("still down")

    with pytest.raises(module.UpstreamUnavailable):
        module.with_retries(unavailable, attempts=3, sleep=slept.append)
    assert transient_calls == 3
    assert slept == [1.0, 2.0]

    protocol_calls = 0

    def invalid_response():
        nonlocal protocol_calls
        protocol_calls += 1
        raise module.UpstreamProtocolError("bad response")

    with pytest.raises(module.UpstreamProtocolError):
        module.with_retries(invalid_response, attempts=3, sleep=lambda _: None)
    assert protocol_calls == 1


def test_soft_404_and_junk_prefixed_zip_are_rejected() -> None:
    module = api()
    entry = archive_entry(module)
    current = head(module)

    with pytest.raises(module.UpstreamDiscoveryError):
        module.verify_downloaded_archive(entry, b"404\n", current)
    with pytest.raises(module.UpstreamDiscoveryError):
        module.verify_downloaded_archive(entry, b"404\n" + valid_zip_bytes(), current)


def test_download_length_must_match_head_content_length() -> None:
    module = api()
    payload = valid_zip_bytes()
    entry = archive_entry(module)
    current = head(module, etag='"etag-new"', length=len(payload) + 1)

    with pytest.raises(module.UpstreamProtocolError):
        module.verify_downloaded_archive(entry, payload, current)


def test_valid_download_records_own_hash_and_does_not_inspect_zip_members(monkeypatch) -> None:
    module = api()
    payload = valid_zip_bytes()
    entry = archive_entry(module)
    current = head(module, etag='"etag-new"')

    def forbidden(*args, **kwargs):
        raise AssertionError("PH2 must not enumerate/read/decompress ZIP members")

    monkeypatch.setattr(zipfile.ZipFile, "infolist", forbidden)
    monkeypatch.setattr(zipfile.ZipFile, "open", forbidden)

    downloaded = module.verify_downloaded_archive(entry, payload, current)

    assert downloaded.sha256 == hashlib.sha256(payload).hexdigest()
    assert downloaded.bytes == len(payload)
    assert downloaded.etag == '"etag-new"'


def test_identical_sha_refreshes_metadata_without_rebuild() -> None:
    module = api()
    payload = valid_zip_bytes()
    entry = archive_entry(module)
    current = head(module, etag='"etag-new"', length=len(payload))
    downloaded = module.verify_downloaded_archive(entry, payload, current)
    locked = fingerprint(
        module,
        sha256=hashlib.sha256(payload).hexdigest(),
        size=len(payload),
        etag='"etag-old"',
    )

    change = module.reconcile_download(locked, downloaded)

    assert change.kind == "metadata-only"
    assert change.requires_rebuild is False
    assert change.etag == '"etag-new"'
    assert change.sha256 == locked.sha256


def test_changed_sha_produces_changed_archive_record() -> None:
    module = api()
    payload = valid_zip_bytes()
    entry = archive_entry(module)
    downloaded = module.verify_downloaded_archive(
        entry,
        payload,
        head(module, etag='"etag-new"', length=len(payload)),
    )

    change = module.reconcile_download(
        fingerprint(module, sha256=SHA_B, size=len(payload)), downloaded
    )

    assert change.kind == "changed"
    assert change.requires_rebuild is True
    assert change.sha256 == hashlib.sha256(payload).hexdigest()


def test_same_hash_with_inconsistent_size_fails_closed() -> None:
    module = api()
    downloaded = module.DownloadedArchive(
        name="riao-ria1",
        sha256=SHA_A,
        bytes=124,
        etag='"etag-new"',
        last_modified=None,
    )

    with pytest.raises(module.UpstreamDiscoveryError):
        module.reconcile_download(fingerprint(module, sha256=SHA_A, size=123), downloaded)
