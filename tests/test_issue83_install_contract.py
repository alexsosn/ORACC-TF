from __future__ import annotations

from pathlib import Path

from oracc_tf import app_generation, distribution


ROOT = Path(__file__).resolve().parents[1]


EXPECTED_DEFAULT_EXCLUSIONS = {
    "catalogue_json",
    "gdl_form",
    "gdl_id",
    "gdl_json",
    "gdl_sexified",
    "inst",
    "lexeme",
    "readingu",
    "ref",
    "sig",
    "sign_json",
    "src_path",
    "translation_source_id",
    "translation_source_license",
    "translation_source_license_url",
    "translation_source_name",
    "translation_source_sha256",
    "translation_source_url",
    "translation_text_raw",
    "word_id",
}


def test_default_browser_preload_exclusions_match_measured_issue83_profile() -> None:
    assert set(app_generation._DEFAULT_BROWSER_EXCLUDED_FEATURES) == (
        EXPECTED_DEFAULT_EXCLUSIONS
    )


def test_standalone_readme_documents_one_clean_local_user_path() -> None:
    readme = distribution._standalone_readme(
        dataset="assyrian-royal-inscriptions",
        release_id="1.0.0",
        tf_version="0.2.0",
    )

    assert "# assyrian-royal-inscriptions" in readme
    assert "1.0.0" in readme
    assert "text-fabric==13.1.0" in readme
    assert "from tf.app import use" in readme
    assert 'use(f"app:{root / \'app\'}")' in readme
    assert 'tf "app:$PWD/app"' in readme
    assert "manifest.json" in readme
    assert "docs/" in readme


def test_researcher_installation_page_records_measured_resource_profile() -> None:
    page = ROOT / "docs" / "reference" / "installation.md"
    assert page.is_file()
    text = page.read_text(encoding="utf-8")
    assert "status: active" in text.split("---", 2)[1]
    assert "text-fabric==13.1.0" in text
    assert "app:" in text
    assert "41.3 MB" in text
    assert "340,824,705" in text  # measured extracted footprint
    assert "388,746,881" in text  # measured post-cache footprint
    assert "1.75 GiB" in text
    assert "38070730938" in text  # traceable CI evidence, not a fabricated benchmark
    assert "measurement-only ZIP" in text
    assert "versioned release-format ZIP" in text


def test_standalone_readme_links_resource_documentation() -> None:
    readme = distribution._standalone_readme(
        dataset="assyrian-royal-inscriptions",
        release_id="1.0.0",
        tf_version="0.2.0",
    )
    assert "docs/reference/installation.md" in readme


def test_researcher_release_status_and_download_example_match_actual_product() -> None:
    """RED contract: do not claim unfinished docs or a nonexistent public asset."""
    root_readme = (ROOT / "README.md").read_text(encoding="utf-8")
    quickstart = (ROOT / "docs/reference/quick-start.md").read_text(
        encoding="utf-8"
    )
    workflow = (ROOT / ".github/workflows/issue83-install-research.yml").read_text(
        encoding="utf-8"
    )
    assert "manual is still being completed" not in root_readme
    assert "Translation import, the standalone app, installation path" not in root_readme
    assert "docs/reference/quick-start.md" in root_readme
    assert "docs/reference/installation.md" in root_readme
    assert "issue #23" in root_readme or "issues/23" in root_readme
    asset = "assyrian-royal-inscriptions-1.0.0.zip"
    assert asset in workflow and asset + ".sha256" in workflow
    for token in (
        "releases/download/v1.0.0",
        asset,
        asset + ".sha256",
        "curl -fL",
        "sha256sum --check",
        "python -m zipfile -e",
        "text-fabric==13.1.0",
    ):
        assert token in quickstart
    assert "not yet public" in quickstart or "not yet published" in quickstart


def test_installation_guide_not_misleading_after_browser_acceptance() -> None:
    page = (ROOT / "docs/reference/installation.md").read_text(encoding="utf-8")
    assert "public feature-help link are tracked\nseparately" not in page
    assert "browser translation" in page
    assert "issues/23" in page
