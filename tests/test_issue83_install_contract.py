from __future__ import annotations

from oracc_tf import app_generation, distribution


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
