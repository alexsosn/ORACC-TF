"""P-002 Phase 0 — version identity and dataset input policy."""

from __future__ import annotations

from pathlib import Path

import pytest

from oracc_tf import releases


SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64


def _archive(name: str, sha256: str, timestamp: str = "2026-08-07T12:00:00") -> releases.ArchiveVersion:
    return releases.ArchiveVersion(name=name, sha256=sha256, oracc_utc_timestamp=timestamp)


def test_source_digest_is_order_independent_but_content_sensitive():
    first = [_archive("riao-ria1", SHA_A), _archive("rinap-rinap1", SHA_B)]
    reordered = list(reversed(first))
    changed = [_archive("riao-ria1", SHA_A), _archive("rinap-rinap1", SHA_C)]

    assert releases.source_set_digest(first) == releases.source_set_digest(reordered)
    assert releases.source_set_digest(first) != releases.source_set_digest(changed)


def test_same_max_timestamp_with_different_archive_bytes_cannot_collide():
    first = releases.ReleaseIdentity.from_archives(
        dataset="assyrian-royal-inscriptions",
        tf_version="1.2.0",
        archives=[_archive("riao-ria1", SHA_A), _archive("rinap-rinap1", SHA_B)],
    )
    changed = releases.ReleaseIdentity.from_archives(
        dataset="assyrian-royal-inscriptions",
        tf_version="1.2.0",
        archives=[_archive("riao-ria1", SHA_A), _archive("rinap-rinap1", SHA_C)],
    )

    assert first.oracc_state == changed.oracc_state == "2026-08-07"
    assert first.source_digest != changed.source_digest
    assert first.tag != changed.tag
    assert first.tag.startswith("assyrian-royal-inscriptions/v1.2.0+oracc.2026-08-07.")
    assert first.tag.endswith(first.source_digest)
    assert changed.tag.endswith(changed.source_digest)


def test_semver_precedence_depends_on_converter_version_not_source_metadata():
    state = [_archive("riao-ria1", SHA_A)]
    v120 = releases.ReleaseIdentity.from_archives("assyrian-royal-inscriptions", "1.2.0", state)
    v121 = releases.ReleaseIdentity.from_archives("assyrian-royal-inscriptions", "1.2.1", state)
    other_source = releases.ReleaseIdentity.from_archives(
        "assyrian-royal-inscriptions",
        "1.2.0",
        [_archive("riao-ria1", SHA_B, "2026-09-01T00:00:00")],
    )

    assert releases.semver_precedence_key(v120.tf_version) < releases.semver_precedence_key(v121.tf_version)
    assert releases.semver_precedence_key(v120.tf_version) == releases.semver_precedence_key(other_source.tf_version)


def test_semver_prerelease_order_matches_the_spec_example():
    ordered = [
        "1.0.0-alpha",
        "1.0.0-alpha.1",
        "1.0.0-alpha.beta",
        "1.0.0-beta",
        "1.0.0-beta.2",
        "1.0.0-beta.11",
        "1.0.0-rc.1",
        "1.0.0",
    ]
    assert sorted(ordered, key=releases.semver_precedence_key) == ordered
    assert releases.semver_precedence_key("1.0.0+build.1") == releases.semver_precedence_key("1.0.0+build.2")


def test_release_identity_rejects_ambiguous_or_invalid_inputs():
    with pytest.raises(releases.ReleaseModelError, match="duplicate archive"):
        releases.ReleaseIdentity.from_archives(
            "assyrian-royal-inscriptions",
            "1.2.0",
            [_archive("riao-ria1", SHA_A), _archive("riao-ria1", SHA_B)],
        )
    with pytest.raises(releases.ReleaseModelError, match="SHA-256"):
        _archive("riao-ria1", "not-a-hash")
    with pytest.raises(releases.ReleaseModelError, match="SemVer"):
        releases.ReleaseIdentity.from_archives(
            "assyrian-royal-inscriptions",
            "1.2",
            [_archive("riao-ria1", SHA_A)],
        )


def test_dataset_config_tracks_only_the_eleven_riao_rinap_archives():
    config = releases.load_datasets(Path("datasets.toml"))
    dataset = config["assyrian-royal-inscriptions"]

    assert dataset.archives == (
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
    assert dataset.tei == ("riao-teiCorpus",)
    assert releases.tracked_archives(config) == frozenset(dataset.archives)
    assert len(releases.tracked_archives(config)) == 11
