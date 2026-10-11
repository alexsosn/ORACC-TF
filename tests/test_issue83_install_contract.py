from __future__ import annotations

from pathlib import Path
import hashlib
import os
import shutil
import subprocess
from zipfile import ZipFile

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
    assert "not yet public" not in quickstart and "not yet published" not in quickstart
    assert "releases/tag/v1.0.0" in quickstart


def test_installation_guide_not_misleading_after_browser_acceptance() -> None:
    page = (ROOT / "docs/reference/installation.md").read_text(encoding="utf-8")
    assert "public feature-help link are tracked\nseparately" not in page
    assert "browser translation" in page
    assert "issues/23" in page


def test_actual_quickstart_shell_fails_closed_and_exits_nonzero(tmp_path: Path) -> None:
    """Exercise shipped Bash snippet, real ZIP/SHA256 tools and mocked downloads."""
    guide = (ROOT / "docs/reference/quick-start.md").read_text(encoding="utf-8")
    fence = chr(96) * 3
    snippet = guide.split(f"{fence}bash\n", 1)[1].split(f"\n{fence}", 1)[0]
    name = "assyrian-royal-inscriptions-1.0.0.zip"
    release_files = tmp_path / "mock-public-release"
    release_files.mkdir()
    archive = release_files / name
    with ZipFile(archive, "w") as bundle:
        bundle.writestr("manifest.json", '{"dataset": "assyrian-royal-inscriptions"}')
    sidecar = release_files / (name + ".sha256")
    valid_digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    sidecar.write_text(f"{valid_digest}  {name}\n", encoding="utf-8")

    # Intercept only curl. Real sha256sum, Python zipfile and Bash flow execute.
    fake_curl = '''
curl() {
  if [ "$ORACC_TEST_CURL_FAIL" = "1" ]; then
    return 22
  fi
  cp "$ORACC_TEST_ASSETS/$(basename "$2")" "$4"
}
'''
    for case in ("failed-download", "bad-hash", "existing-directory", "success"):
        work = tmp_path / case
        work.mkdir()
        env = os.environ.copy()
        env.update(
            ORACC_TEST_ASSETS=str(release_files),
            ORACC_TEST_CURL_FAIL="1" if case == "failed-download" else "0",
        )
        extracted = work / "assyrian-royal-inscriptions"
        if case == "failed-download":
            # Stale local files would pass SHA256 if HTTP failures are ignored.
            shutil.copy2(archive, work / name)
            shutil.copy2(sidecar, work / (name + ".sha256"))
        if case == "bad-hash":
            sidecar.write_text(f"{'0' * 64}  {name}\n", encoding="utf-8")
        if case == "existing-directory":
            extracted.mkdir()
            (extracted / "do-not-overwrite.txt").write_text("old", encoding="utf-8")
        if case in {"existing-directory", "success"}:
            sidecar.write_text(f"{valid_digest}  {name}\n", encoding="utf-8")

        result = subprocess.run(
            ["bash", "-c", fake_curl + "\n" + snippet],
            cwd=work,
            env=env,
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )
        if case == "success":
            assert result.returncode == 0, result.stderr
            assert (extracted / "manifest.json").is_file()
        else:
            assert result.returncode != 0, (
                f"{case} incorrectly reported shell success: {result.stderr}"
            )
            assert not (extracted / "manifest.json").exists(), (
                f"{case} incorrectly extracted the archive"
            )


def test_published_v1_reader_docs_match_real_release_not_measurement_zip() -> None:
    """RED: published GitHub Release has separate, precise asset identity."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    quick = (ROOT / "docs/reference/quick-start.md").read_text(encoding="utf-8")
    install = (ROOT / "docs/reference/installation.md").read_text(encoding="utf-8")
    citation = (ROOT / "docs/reference/citation.md").read_text(encoding="utf-8")

    tag = "https://github.com/alexsosn/ORACC-TF/releases/tag/v1.0.0"
    digest = "788f580604e30054fab34c4c3ea60ec3eb4f399412f1da90f778469d03507468"
    assert tag in readme and tag in quick and tag in install
    assert "Public release publication and clean acquisition from the public asset are" not in readme
    assert "enable `publish_1_0`" not in readme
    assert "already exists" in readme
    assert "41,285,702" in install  # exact published archive size, not benchmark ZIP
    assert digest in install
    assert "measurement-only" in install
    assert "38128162676" in install  # actual publishing run
    assert "published" in citation.lower() and tag in citation
    assert "when one exists" not in install
    assert "v1.0.0 public asset already exists" not in install
    # The public ZIP is immutable; updating main documentation does not
    # rewrite its originally bundled manual.
    assert "immutable" in readme.lower()
