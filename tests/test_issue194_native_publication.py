"""P0 RED-first public ETCSRI/NINMED release authorization and delivery gates.

Source-complete candidate tests live under issue #196. This ticket proves an
explicit final release ID and refuses GitHub Release publication from PR
merge commits, absent consumer tests, or unverified public bytes.
"""
from __future__ import annotations

from pathlib import Path
import json
import runpy
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts/build_native_releases.py"
WORKFLOW = ROOT / ".github/workflows/issue194-native-publication.yml"


def test_final_release_identity_is_explicit_and_invalid_ids_fail_closed(tmp_path: Path) -> None:
    assert BUILDER.is_file()
    namespace = runpy.run_path(str(BUILDER), run_name="_test_only_")
    build = namespace["build_candidate"]
    with pytest.raises(ValueError, match="invalid release_id"):
        build(
            ROOT, tmp_path / "out", kind="etcsri",
            builder_commit="a" * 40, release_id="../../escape",
        )

    help_text = subprocess.run(
        [sys.executable, str(BUILDER), "--help"],
        check=True, text=True, capture_output=True,
    ).stdout
    assert "--release-id" in help_text
    assert "0.1.0" in help_text


def test_public_release_workflow_can_only_publish_from_reviewed_main() -> None:
    assert WORKFLOW.is_file()
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "branches: [main]" in text
    assert "github.event_name == 'push'" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert "--release-id 0.1.0" in text
    assert "gh release create native-v0.1.0" in text
    assert "contents: write" in text
    assert "needs:" in text and "clean-user" in text
    assert "actions/download-artifact@v4" in text
    assert "sha256sum -c" in text
    assert "curl --fail --location" in text
    assert "etcsri-0.1.0.zip" in text
    assert "ninmed-0.1.0.zip" in text
    assert "etcsri-0.1.0.zip.sha256" in text
    assert "ninmed-0.1.0.zip.sha256" in text
    assert "if-no-files-found: error" in text


def test_releases_are_never_advertised_as_standalone_before_public_http_verification() -> None:
    assert WORKFLOW.is_file()
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "verify-public" in source
    assert "releases/download/native-v0.1.0" in source
    assert "sha256sum -c" in source
    assert "manifest.json" in source
    assert "tf.app" in source or "from tf.app import use" in source
    assert "text-fabric==13.1.0" in source


def test_publication_pins_exact_reviewed_json_source_states_not_only_counts() -> None:
    """A same-size source edit is still a new edition and must stop publication."""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert (
        "sha256:1a1dc3e8f23a1126b578a7c3c459ef928c1d3dc1ad161af9a77c93f6763cc382"
        in workflow
    )
    assert (
        "sha256:2c8e9bcc583c2900698811af1a5a8123289d1303aa16c8c107b704461ecf422b"
        in workflow
    )
    # The manifest is checked against the expected immutable snapshot in
    # both the pre-publication clean reader and public HTTP consumer jobs.
    assert workflow.count('assert manifest["source_state"] == reviewed[kind]') == 2


def test_researcher_readme_links_both_actual_public_native_assets_and_first_use() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "https://github.com/alexsosn/ORACC-TF/releases/tag/native-v0.1.0" in readme
    for corpus in ("etcsri", "ninmed"):
        base = ("https://github.com/alexsosn/ORACC-TF/releases/download/"
                f"native-v0.1.0/{corpus}-0.1.0.zip")
        assert base in readme
        assert base + ".sha256" in readme
    assert "sha256sum -c" in readme
    assert "python -m tf.browser.start" in readme
    for false_claim in (
        "Neither native corpus has a public standalone TF ZIP yet",
        "not an announced public ETCSRI dataset archive",
        "not a published NINMED corpus archive",
        "A **local, unpublished** Text-Fabric browser app",
    ):
        assert false_claim not in readme


def test_native_researcher_indexes_refer_to_exact_published_assets() -> None:
    for corpus in ("etcsri", "ninmed"):
        text = (ROOT / "docs" / "native" / corpus / "index.md").read_text(
            encoding="utf-8"
        )
        direct = ("https://github.com/alexsosn/ORACC-TF/releases/download/"
                  f"native-v0.1.0/{corpus}-0.1.0.zip")
        assert direct in text
        assert direct + ".sha256" in text
        assert "text-fabric==13.1.0" in text
        assert "TFQL" in text


def test_closed_native_release_tasks_are_not_open_in_agent_registry() -> None:
    registry = json.loads((ROOT / "docs" / "registry.json").read_text(encoding="utf-8"))
    for issue in (194, 196):
        task = next(row for row in registry["tasks"] if row.get("issue") == issue)
        assert task["status"] == "done"
        evidence = ROOT / task["evidence_file"]
        assert evidence.is_file(), task["id"]
        record = json.loads(evidence.read_text(encoding="utf-8"))
        assert record["status"] == "done"
        assert record["issue"] == issue
    status = json.loads((ROOT / "docs/task-state/ISSUE-194.json").read_text())
    assert status["publication"]["tag"] == "native-v0.1.0"
    assert status["publication"]["verification_run"] == 44377078649
