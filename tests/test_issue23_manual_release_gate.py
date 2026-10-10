"""RED: manually gated publication of a tested 1.0 candidate (#23)."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
FLOW = ROOT / ".github/workflows/issue83-install-research.yml"


def _workflow() -> dict:
    # BaseLoader retains the YAML "on" key; safe_load treats it as bool (YAML 1.1).
    return yaml.load(FLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_public_1_0_release_has_explicit_off_by_default_manual_gate() -> None:
    flow = _workflow()
    inputs = flow["on"]["workflow_dispatch"]["inputs"]
    gate = inputs["publish_1_0"]
    assert gate["type"] == "boolean"
    assert gate["default"] == "false"
    assert flow["permissions"]["contents"] == "read"
    assert "pull_request" in flow["on"]


def test_release_job_only_on_main_and_after_full_corpus_checks() -> None:
    jobs = _workflow()["jobs"]
    publish = jobs["publish-release"]
    assert publish["needs"] == "standalone-candidate"
    assert publish["permissions"]["contents"] == "write"
    expression = publish["if"]
    for condition in (
        "github.event_name == 'workflow_dispatch'",
        "github.ref == 'refs/heads/main'",
        "inputs.publish_1_0",
    ):
        assert condition in expression
    assert jobs["standalone-candidate"].get("permissions", {}).get("contents", "read") != "write"


def test_release_identity_asset_upload_and_public_download_verified() -> None:
    flow = _workflow()
    jobs = flow["jobs"]
    build = "\n".join(str(step.get("run", "")) for step in jobs["standalone-candidate"]["steps"])
    assert '"1.0.0"' in build
    assert "publish_1_0" in build or "ORACC_TF_PUBLISH_1_0" in build

    publish = "\n".join(str(step.get("run", "")) for step in jobs["publish-release"]["steps"])
    assert "actions/download-artifact@v4" in str(jobs["publish-release"]["steps"])
    assert "sha256sum -c" in publish
    assert 'gh release create "v1.0.0"' in publish
    assert "assyrian-royal-inscriptions-1.0.0.zip" in publish
    assert "curl" in publish and "releases/download/v1.0.0" in publish
    assert "gh release view" in publish  # fail closed for a preexisting public release


def test_publication_manual_does_not_ship_stale_pre_release_claims() -> None:
    """The same canonical docs are shipped in the 1.0 ZIP after dispatch."""
    pages = {
        "README.md": ROOT / "README.md",
        "reference-index": ROOT / "docs/reference/index.md",
        "citation": ROOT / "docs/reference/citation.md",
        "known-issues": ROOT / "docs/reference/known-issues.md",
    }
    for label, path in pages.items():
        text = path.read_text(encoding="utf-8").lower()
        assert "is pre-1.0" not in text, label
        assert "not yet published" not in text, label
        assert "has not been published" not in text, label
        assert "release does not yet exist" not in text, label
        assert "pre-1.0 release candidate" not in text, label
    assert "manifest.json" in pages["reference-index"].read_text(encoding="utf-8")


def test_researcher_publication_instructions_do_not_use_abstract_repo_as_url() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "manifest.repository" in text
    assert "ORACC-TF-assyrian-royal-inscriptions" in text
    assert "logical" in text.lower()
    assert "https://github.com/alexsosn/ORACC-TF/releases" in text


def test_public_archive_pins_feature_help_to_same_builder_commit_as_manifest() -> None:
    flow = _workflow()
    build = "\n".join(
        str(step.get("run", ""))
        for step in flow["jobs"]["standalone-candidate"]["steps"]
    )
    assert 'docs_ref=os.environ["GITHUB_SHA"]' in build
    assert 'builder_commit=os.environ["GITHUB_SHA"]' in build
    assert 'Path("docs/reference/features.md").is_file()' in build
    assert "publish_1_0" in str(flow["on"]["workflow_dispatch"]["inputs"])


def test_first_user_quick_start_is_valid_before_and_after_publication() -> None:
    quick = (ROOT / "docs/reference/quick-start.md").read_text(encoding="utf-8")
    assert "until a release asset exists" not in quick.lower()
    assert "this is an installation *candidate*" not in quick.lower()
    assert "https://github.com/alexsosn/ORACC-TF/releases" in quick
    assert "manifest.json" in quick
    assert "checksum" in quick.lower()
    assert "CI" in quick or "staged" in quick.lower()  # distinguish candidate from public asset


def test_publish_fails_closed_when_pinned_public_feature_help_is_missing() -> None:
    flow = _workflow()
    publish_steps = flow["jobs"]["publish-release"]["steps"]
    upload = next(
        str(step.get("run", ""))
        for step in publish_steps
        if "gh release create" in str(step.get("run", ""))
    )
    assert "raw.githubusercontent.com/$GITHUB_REPOSITORY/$GITHUB_SHA/docs/reference/features.md" in upload
    assert "curl --fail" in upload
    assert "word_lex" in upload
    assert upload.index("raw.githubusercontent.com") < upload.index("gh release create")
