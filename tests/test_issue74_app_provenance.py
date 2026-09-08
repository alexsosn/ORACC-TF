"""ISSUE-74 RED contracts for app provenance and official ORACC source links."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
DATASET = "assyrian-royal-inscriptions"
REPOSITORY = "ORACC-TF-assyrian-royal-inscriptions"
RELEASE_ID = "2026.09.08-test"
TF_VERSION = "0.2.0"
BUILDER_COMMIT = "b096e75483a3a07e2bcaa948da9ffdd3fc56bf77"
SOURCE_STATE = "sha256:" + "a" * 64
TREE_DIGEST = "sha256:" + "b" * 64


def api():
    return importlib.import_module("oracc_tf.app_provenance")


def manifest(*, source_state: str | None = SOURCE_STATE) -> dict[str, object]:
    record = {
        "tf_version": TF_VERSION,
        "tf_root": f"{DATASET}/tf/{TF_VERSION}",
        "builder_commit": BUILDER_COMMIT,
        "source_state": source_state,
        "provenance_complete": source_state is not None,
        "tree_digest": TREE_DIGEST,
    }
    return {
        "schema_version": 3,
        "dataset": DATASET,
        "repository": REPOSITORY,
        "release_id": RELEASE_ID,
        **record,
        "releases": {RELEASE_ID: dict(record)},
        "visible_roots": {record["tf_root"]: RELEASE_ID},
    }


def test_release_provenance_comes_from_current_manifest_record_and_serializes_stably() -> None:
    module = api()
    payload = manifest()

    record = module.release_provenance(payload)

    assert record.dataset == DATASET
    assert record.repository == REPOSITORY
    assert record.release_id == RELEASE_ID
    assert record.tf_version == TF_VERSION
    assert record.builder_commit == BUILDER_COMMIT
    assert record.source_state == SOURCE_STATE
    assert record.tree_digest == TREE_DIGEST

    first = module.render_release_provenance(record)
    second = module.render_release_provenance(module.release_provenance(payload))
    assert first == second
    assert first.endswith(b"\n")
    decoded = json.loads(first)
    assert decoded == {
        "builder_commit": BUILDER_COMMIT,
        "dataset": DATASET,
        "release_id": RELEASE_ID,
        "repository": REPOSITORY,
        "source_state": SOURCE_STATE,
        "tf_version": TF_VERSION,
        "tree_digest": TREE_DIGEST,
    }
    assert "doi" not in decoded
    assert "license" not in decoded


def test_incomplete_source_state_remains_explicitly_unknown_without_fabricated_claims() -> None:
    module = api()

    record = module.release_provenance(manifest(source_state=None))
    decoded = json.loads(module.render_release_provenance(record))

    assert record.source_state is None
    assert decoded["source_state"] is None
    assert "doi" not in decoded
    assert "license" not in decoded


def test_release_provenance_rejects_unsupported_schema_and_current_ledger_drift() -> None:
    module = api()

    bad_schema = manifest()
    bad_schema["schema_version"] = 2
    with pytest.raises(module.AppProvenanceError):
        module.release_provenance(bad_schema)

    missing_release = manifest()
    missing_release["release_id"] = "not-in-ledger"
    with pytest.raises(module.AppProvenanceError):
        module.release_provenance(missing_release)

    mismatched_builder = manifest()
    releases = mismatched_builder["releases"]
    assert isinstance(releases, dict)
    current = releases[RELEASE_ID]
    assert isinstance(current, dict)
    current["builder_commit"] = "c" * 40
    with pytest.raises(module.AppProvenanceError):
        module.release_provenance(mismatched_builder)

    mismatched_source = manifest()
    releases = mismatched_source["releases"]
    assert isinstance(releases, dict)
    current = releases[RELEASE_ID]
    assert isinstance(current, dict)
    current["source_state"] = "sha256:" + "d" * 64
    current["provenance_complete"] = True
    with pytest.raises(module.AppProvenanceError):
        module.release_provenance(mismatched_source)


def test_release_provenance_rejects_noncanonical_tf_version_even_when_paths_agree() -> None:
    module = api()
    payload = manifest()
    bad_version = "../x"
    bad_root = f"{DATASET}/tf/{bad_version}"
    payload["tf_version"] = bad_version
    payload["tf_root"] = bad_root
    releases = payload["releases"]
    assert isinstance(releases, dict)
    current = releases[RELEASE_ID]
    assert isinstance(current, dict)
    current["tf_version"] = bad_version
    current["tf_root"] = bad_root
    payload["visible_roots"] = {bad_root: RELEASE_ID}

    with pytest.raises(module.AppProvenanceError):
        module.release_provenance(payload)


def _source_doc(subproject: str) -> dict[str, object]:
    path = ROOT / "data" / subproject / "corpusjson" / "Q003840.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_real_bare_q_collision_resolves_through_source_qualified_project_urls() -> None:
    module = api()
    rinap5 = _source_doc("rinap/rinap5")
    rinap5p1 = _source_doc("rinap/rinap5p1")

    url5 = module.official_document_url(
        subproject="rinap/rinap5",
        text_id="Q003840",
        source_url=rinap5.get("source"),
        source_project=rinap5.get("project"),
    )
    url5p1 = module.official_document_url(
        subproject="rinap/rinap5p1",
        text_id="Q003840",
        source_url=rinap5p1.get("source"),
        source_project=rinap5p1.get("project"),
    )

    assert url5 == "http://oracc.org/rinap/rinap5/Q003840/"
    assert url5p1 == "http://oracc.org/rinap/rinap5p1/Q003840/"
    assert url5 != url5p1


def test_missing_source_url_omits_link_instead_of_guessing_from_bare_q() -> None:
    module = api()

    assert module.official_document_url(
        subproject="rinap/rinap5",
        text_id="Q003840",
        source_url=None,
        source_project="rinap/rinap5",
    ) is None


@pytest.mark.parametrize(
    ("subproject", "text_id", "source_url", "source_project"),
    [
        ("rinap/rinap5", "Q003840", "http://oracc.org/rinap/rinap5p1", "rinap/rinap5"),
        ("rinap/rinap5", "Q003840", "http://oracc.org/rinap/rinap5", "rinap/rinap5p1"),
        ("rinap/rinap5", "Q3840", "http://oracc.org/rinap/rinap5", "rinap/rinap5"),
        ("rinap/rinap5", "Q003840", "ftp://oracc.org/rinap/rinap5", "rinap/rinap5"),
        ("rinap/rinap5", "Q003840", "https://example.com/rinap/rinap5", "rinap/rinap5"),
        ("rinap/rinap5", "Q003840", "https://user@oracc.org/rinap/rinap5", "rinap/rinap5"),
        ("rinap/rinap5", "Q003840", "https://oracc.org/rinap/rinap5?x=1", "rinap/rinap5"),
        ("rinap/rinap5", "Q003840", "https://oracc.org/rinap/rinap5#frag", "rinap/rinap5"),
        ("rinap/rinap5", "Q003840", "http://oracc.org/rinap/\trinap5", "rinap/rinap5"),
    ],
)
def test_source_link_validation_fails_closed(
    subproject: str,
    text_id: str,
    source_url: str,
    source_project: str,
) -> None:
    module = api()

    with pytest.raises(module.AppProvenanceError):
        module.official_document_url(
            subproject=subproject,
            text_id=text_id,
            source_url=source_url,
            source_project=source_project,
        )


def test_no_lexeme_link_api_is_exposed_without_stable_official_identity() -> None:
    module = api()

    assert not hasattr(module, "official_lexeme_url")
