"""ISSUE-42 RED contracts for independent TEI upstream discovery/state selection."""

from __future__ import annotations

from datetime import date
import importlib

import pytest


RIAO_LISTING = "https://oracc.example/riao/downloads/"
RINAP_LISTING = "https://oracc.example/rinap/downloads/"
SHA_A = "a" * 64
SHA_B = "b" * 64


def api():
    return importlib.import_module("oracc_tf.tei_upstream")


def _candidate(module, html: str, listing_url: str = RIAO_LISTING):
    candidates = module.parse_download_listing(html, listing_url)
    assert len(candidates) == 1
    return candidates[0]


def _verified(module, candidate, sha256: str = SHA_A, size: int = 123):
    return module.VerifiedTeiCandidate(
        candidate=candidate,
        sha256=sha256,
        bytes=size,
    )


def test_multiple_dated_exports_select_the_newest_cohort() -> None:
    module = api()
    html = """
    <a href="riao-teiCorpus-20231201.zip">old</a>
    <a href="riao-teiCorpus-20241202.zip">new</a>
    <a href="cat.geojson">ignore</a>
    """

    candidates = module.parse_download_listing(html, RIAO_LISTING)
    cohort = module.newest_candidate_cohort(candidates)

    assert [item.name for item in cohort] == ["riao-teiCorpus-20241202.zip"]
    assert cohort[0].source_prefix == "riao"
    assert cohort[0].published_date == date(2024, 12, 2)
    assert cohort[0].url == RIAO_LISTING + "riao-teiCorpus-20241202.zip"


@pytest.mark.parametrize(
    "href",
    [
        "riao-teiCorpus-latest.zip",
        "riao-teiCorpus-20241301.zip",
        "riao-teiCorpus-20240230.zip",
        "-teiCorpus-20240101.zip",
    ],
)
def test_candidate_like_malformed_names_and_dates_fail_closed(href: str) -> None:
    module = api()

    with pytest.raises(module.TeiDiscoveryError):
        module.parse_download_listing(f'<a href="{href}">candidate</a>', RIAO_LISTING)


def test_candidate_order_is_stable_and_duplicate_hrefs_are_idempotent() -> None:
    module = api()
    html_a = """
    <a href="riao-teiCorpus-20241202.zip">new</a>
    <a href="riao-teiCorpus-20240101.zip">old</a>
    <a href="riao-teiCorpus-20241202.zip">new duplicate</a>
    """
    html_b = """
    <a href="riao-teiCorpus-20240101.zip">old</a>
    <a href="riao-teiCorpus-20241202.zip">new</a>
    """

    parsed_a = module.parse_download_listing(html_a, RIAO_LISTING)
    parsed_b = module.parse_download_listing(html_b, RIAO_LISTING)

    assert parsed_a == parsed_b
    assert len(parsed_a) == 2


def test_same_date_different_hashes_are_ambiguous() -> None:
    module = api()
    riao = _candidate(
        module,
        '<a href="riao-teiCorpus-20241202.zip">riao</a>',
        RIAO_LISTING,
    )
    rinap = _candidate(
        module,
        '<a href="rinap-teiCorpus-20241202.zip">rinap</a>',
        RINAP_LISTING,
    )
    cohort = module.newest_candidate_cohort((riao, rinap))

    with pytest.raises(module.AmbiguousTeiSource):
        module.resolve_verified_cohort(
            "riao-teiCorpus",
            cohort,
            (
                _verified(module, riao, SHA_A),
                _verified(module, rinap, SHA_B),
            ),
        )


def test_same_date_same_bytes_collapse_to_one_state_with_all_aliases() -> None:
    module = api()
    riao = _candidate(
        module,
        '<a href="riao-teiCorpus-20241202.zip">riao</a>',
        RIAO_LISTING,
    )
    rinap = _candidate(
        module,
        '<a href="rinap-teiCorpus-20241202.zip">rinap</a>',
        RINAP_LISTING,
    )
    cohort = module.newest_candidate_cohort((rinap, riao))

    state = module.resolve_verified_cohort(
        "riao-teiCorpus",
        cohort,
        (
            _verified(module, rinap, SHA_A, 456),
            _verified(module, riao, SHA_A, 456),
        ),
    )

    assert state.logical_source == "riao-teiCorpus"
    assert state.sha256 == SHA_A
    assert state.bytes == 456
    assert tuple(alias.name for alias in state.aliases) == (
        "riao-teiCorpus-20241202.zip",
        "rinap-teiCorpus-20241202.zip",
    )


def test_missing_verification_for_a_same_date_candidate_fails_closed() -> None:
    module = api()
    riao = _candidate(
        module,
        '<a href="riao-teiCorpus-20241202.zip">riao</a>',
        RIAO_LISTING,
    )
    rinap = _candidate(
        module,
        '<a href="rinap-teiCorpus-20241202.zip">rinap</a>',
        RINAP_LISTING,
    )
    cohort = module.newest_candidate_cohort((riao, rinap))

    with pytest.raises(module.TeiDiscoveryError):
        module.resolve_verified_cohort(
            "riao-teiCorpus",
            cohort,
            (_verified(module, riao, SHA_A),),
        )


def test_newer_filename_with_identical_bytes_is_metadata_only() -> None:
    module = api()
    old = _candidate(
        module,
        '<a href="riao-teiCorpus-20240101.zip">old</a>',
    )
    new = _candidate(
        module,
        '<a href="riao-teiCorpus-20241202.zip">new</a>',
    )
    old_state = module.resolve_verified_cohort(
        "riao-teiCorpus", (old,), (_verified(module, old, SHA_A),)
    )
    new_state = module.resolve_verified_cohort(
        "riao-teiCorpus", (new,), (_verified(module, new, SHA_A),)
    )

    assert module.compare_source_state(old_state, new_state) == "metadata-only"


def test_changed_bytes_are_a_semantic_source_change() -> None:
    module = api()
    old = _candidate(
        module,
        '<a href="riao-teiCorpus-20240101.zip">old</a>',
    )
    new = _candidate(
        module,
        '<a href="riao-teiCorpus-20241202.zip">new</a>',
    )
    old_state = module.resolve_verified_cohort(
        "riao-teiCorpus", (old,), (_verified(module, old, SHA_A),)
    )
    new_state = module.resolve_verified_cohort(
        "riao-teiCorpus", (new,), (_verified(module, new, SHA_B),)
    )

    assert module.compare_source_state(old_state, new_state) == "changed"


def test_riao_rinap_overlap_fixture_uses_date_not_prefix_as_selection_signal() -> None:
    module = api()
    riao = module.parse_download_listing(
        '<a href="riao-teiCorpus-20241202.zip">newer RIAO export</a>',
        RIAO_LISTING,
    )
    rinap = module.parse_download_listing(
        '<a href="rinap-teiCorpus-20190823.zip">older RINAP export</a>',
        RINAP_LISTING,
    )
    all_candidates = (*riao, *rinap)

    cohort = module.newest_candidate_cohort(all_candidates)

    assert {item.name for item in all_candidates} == {
        "riao-teiCorpus-20241202.zip",
        "rinap-teiCorpus-20190823.zip",
    }
    assert [item.name for item in cohort] == ["riao-teiCorpus-20241202.zip"]


def test_unavailable_listing_is_a_typed_failure() -> None:
    module = api()

    with pytest.raises(module.TeiListingUnavailable):
        module.parse_download_listing(None, RIAO_LISTING)
