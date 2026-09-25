"""M9 translation source is part of the registered release build."""

from __future__ import annotations

from pathlib import Path

import pytest

from oracc_tf import corpus, paths, publishing, translations


def test_registered_builder_fails_closed_without_pinned_tei_source(tmp_path, monkeypatch):
    monkeypatch.delenv("ORACC_TF_M9_TEI_ARCHIVE", raising=False)

    def should_not_build(*args, **kwargs):
        raise RuntimeError("builder must not run without the pinned TEI source")

    monkeypatch.setattr(corpus, "build_full_tf", should_not_build)

    with pytest.raises(ValueError, match="pinned TEI archive"):
        publishing.build_registered_tf(
            tmp_path,
            "assyrian-royal-inscriptions",
        )


def test_registered_builder_parses_and_passes_pinned_tei_map(tmp_path, monkeypatch):
    archive = tmp_path / translations.OFFICIAL_ARCHIVE_NAME
    expected_map = {"riao/ria1:Q001801": (object(),)}
    observed = {}

    class Index:
        def as_document_map(self):
            return expected_map

    def parse(path):
        observed["archive"] = Path(path)
        return Index()

    def build(out_dir, *, data, translations_by_document):
        observed["build"] = (Path(out_dir), Path(data), translations_by_document)
        return "report"

    monkeypatch.setattr(translations, "parse_tei_archive", parse)
    monkeypatch.setattr(corpus, "build_full_tf", build)

    root, report = publishing.build_registered_tf(
        tmp_path,
        "assyrian-royal-inscriptions",
        translations_archive=archive,
    )

    assert root == paths.publishable_tf_root(
        tmp_path, "assyrian-royal-inscriptions", publishing.TF_VERSION
    )
    assert report == "report"
    assert observed["archive"] == archive
    assert observed["build"] == (root, paths.DATA, expected_map)


def test_registered_builder_uses_pinned_archive_environment_path(tmp_path, monkeypatch):
    archive = tmp_path / translations.OFFICIAL_ARCHIVE_NAME
    monkeypatch.setenv("ORACC_TF_M9_TEI_ARCHIVE", str(archive))
    observed = {}

    class Index:
        def as_document_map(self):
            return {}

    def parse(path):
        observed["archive"] = Path(path)
        return Index()

    monkeypatch.setattr(translations, "parse_tei_archive", parse)
    monkeypatch.setattr(corpus, "build_full_tf", lambda *args, **kwargs: "report")

    publishing.build_registered_tf(tmp_path, "assyrian-royal-inscriptions")

    assert observed["archive"] == archive
