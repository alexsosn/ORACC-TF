"""P0 RED-first public ETCSRI/NINMED release authorization and delivery gates.

Source-complete candidate tests live under issue #196. This ticket proves an
explicit final release ID and refuses GitHub Release publication from PR
merge commits, absent consumer tests, or unverified public bytes.
"""
from __future__ import annotations

from pathlib import Path
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
