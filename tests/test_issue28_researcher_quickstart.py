"""RED-first acceptance checks for issue #28's first-user reference pages."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "docs" / "reference"


def _text(name: str) -> str:
    return (REF / name).read_text(encoding="utf-8")


def _blocks(name: str) -> list[str]:
    return [
        chunk.split("```", 1)[0]
        for chunk in _text(name).split("```python")[1:]
    ]


def test_first_user_quick_start_is_active_and_standalone() -> None:
    text = _text("quick-start.md")
    assert "status: active" in text
    assert "RIAO" in text and "RINAP" in text
    assert "text-fabric==13.1.0" in text
    assert "from tf.app import use" in text
    assert "app:" in text and "A.api" in text
    assert "document_key" in text
    assert "oracc_tf" not in text
    assert "docs/reference/installation.md" not in text  # relative reader links
    assert "](" in text and "installation.md" in text
    assert "model.md" in text and "translations.md" in text


def test_query_guide_compiles_and_uses_current_public_graph() -> None:
    text = _text("query-guide.md")
    assert "status: active" in text
    for surface in (
        "document_key", "L.d", "word_lex", "translation_line",
        "translation_sref", "translation_eref", "ruler", "period",
        "synthetic", "sign_json",
    ):
        assert surface in text
    assert "rinap5p1" in text  # real official TEI coverage hole
    blocks = _blocks("query-guide.md")
    assert len(blocks) >= 4
    for block in blocks:
        compile(block, "query-guide.md", "exec")
        assert "from oracc_tf" not in block
        assert "F.break" not in block
        assert "line.translation" not in block


def test_reproducibility_distinguishes_release_and_maintainer_paths() -> None:
    text = _text("reproducibility.md")
    assert "status: active" in text
    for field in ("manifest.json", "source_state", "builder_commit", "tf_version"):
        assert field in text
    assert "ISSUE-124" in text
    assert "riao-teiCorpus-20241202.zip" in text
    assert "b793d8920db58908e3a044b7f2d1a204c1ba0784e880007e0cd7941333e841bd" in text
    assert "CC0" in text and "CC BY-SA" in text
    assert "rebuild" in text.lower() and "release" in text.lower()
    for block in _blocks("reproducibility.md"):
        compile(block, "reproducibility.md", "exec")


def test_reference_landing_has_direct_first_user_navigation() -> None:
    index = _text("index.md")
    for name in (
        "quick-start.md", "query-guide.md", "reproducibility.md",
        "features.md", "model.md", "signs.md", "words-and-lexemes.md",
        "identity.md", "translations.md", "data-audit.md",
    ):
        assert f"]({name})" in index


def test_p003_ph2_does_not_wait_on_full_p002_upstream_automation() -> None:
    registry = json.loads((ROOT / "docs" / "registry.json").read_text(encoding="utf-8"))
    task = next(x for x in registry["tasks"] if x["id"] == "P-003.PH2")
    assert "P-002.PH1" not in task.get("completion_blocked_by", [])

# Exercise published examples against real ORACC source, not fabricated TF mocks.
import pytest


@pytest.mark.corpus
def test_published_first_passage_and_query_recipes_on_real_source(tmp_path) -> None:
    import os
    from tf.fabric import Fabric
    from oracc_tf import corpus, loader, metadata, paths, translations

    archive = os.environ.get("ORACC_TF_M9_TEI_ARCHIVE")
    if not archive:
        pytest.skip("pinned official TEI archive required for translation-range replay")
    translation_index = translations.parse_tei_archive(archive)

    source_paths = (
        "riao/ria1/corpusjson/Q001801.json",
        "riao/ria5/corpusjson/Q009276.json",
        "rinap/rinap4/corpusjson/Q003333.json",
        "rinap/rinap5/corpusjson/Q003840.json",
        "rinap/rinap5p1/corpusjson/Q003840.json",
    )
    if any(not (paths.DATA / rel).is_file() for rel in source_paths):
        pytest.skip("official source subset unavailable")

    root = tmp_path / "tf"
    corpus.build_tf(
        root,
        editions=[loader.load_edition(paths.DATA / rel) for rel in source_paths],
        translations_by_document=translation_index.as_document_map(),
        metadata_index=metadata.load_index(
            paths.DATA,
            subprojects=(
                "riao/ria1", "riao/ria5", "rinap/rinap4",
                "rinap/rinap5", "rinap/rinap5p1",
            ),
        ),
    )
    tf = Fabric(locations=str(root), silent="deep")
    assert tf.loadAll(silent="deep")
    api = tf.api
    assert api is not None

    # First-user setup uses a standalone app; its consumer API should work with
    # this independently built TF graph too. Replay only user query blocks.
    quick = _blocks("quick-start.md")
    assert len(quick) >= 3
    env = {"api": api}
    for block in quick[1:3]:
        exec(compile(block, "quick-start.md", "exec"), env)
    assert api.F.document_key.v(env["doc"]) == "riao/ria1:Q001801"
    assert env["words"]

    recipes = _blocks("query-guide.md")
    assert len(recipes) >= 5
    for block in recipes[:4]:
        exec(compile(block, "query-guide.md", "exec"), env)
    assert env["passage"]
    assert env["occurrences"]  # real source contains mātu[land]N
    assert isinstance(env["reigns"].most_common(10), list)
    assert isinstance(env["ranges_and_text"], list)
