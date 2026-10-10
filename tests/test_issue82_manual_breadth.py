"""RED-first issue #82 researcher-manual coverage of real user workflows."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "docs" / "reference"

def page(name: str) -> str:
    return (REF / name).read_text(encoding="utf-8")

def python_blocks(text: str) -> list[str]:
    return [part.split("```", 1)[0] for part in text.split("```python")[1:]]


def test_corpus_scope_names_registered_inclusions_and_exclusions() -> None:
    text = page("scope.md")
    assert "status: active" in text
    for term in ("RIAO", "RINAP", "rinap5p1", "scores", "sources", "corpusjson", "TEI", "document_key"):
        assert term in text
    assert "model.md" in text and "data-audit.md" in text


def test_actual_public_text_format_names_and_empty_sign_semantics() -> None:
    text = page("text-formats.md")
    assert "status: active" in text
    for term in ("text-orig-full", "text-trans-full", "lex-default", "utf8", "cuneiform_trailer", "form", "cf", "gw", "synthetic=1"):
        assert term in text
    assert "T.text" in text
    assert "signs.md" in text
    blocks = python_blocks(text)
    assert len(blocks) >= 1
    for block in blocks:
        compile(block, "text-formats.md", "exec")


def test_supported_browser_entrypoint_not_fictitious_offline_docs() -> None:
    text = page("browser.md")
    assert "status: active" in text
    assert 'tf "app:$PWD/app"' in text
    assert "passage" in text and "query" in text and "export" in text
    assert "feature" in text and "GitHub" in text
    assert "offline" in text.lower() and "publication" in text.lower()
    assert "installation.md" in text and "query-guide.md" in text


def test_acknowledgements_and_references_cite_upstream_scholarship() -> None:
    bibliography = page("references.md")
    credit = page("acknowledgements.md")
    assert "status: active" in bibliography and "status: active" in credit
    for term in ("ORACC", "RIAO", "RINAP", "Text-Fabric", "Assyrian Rulers of the Third and Second Millennia BC", "1987"):
        assert term in bibliography
    for term in ("Grayson", "Novotny", "Morello", "Q001801", "ORACC-TF"):
        assert term in credit
    assert "citation.md" in credit and "citation.md" in bibliography


def test_no_unpublished_release_claim_or_development_checkout_dependency() -> None:
    for filename in ("scope.md", "text-formats.md", "browser.md", "references.md", "acknowledgements.md"):
        text = page(filename)
        assert "from oracc_tf" not in text
        assert "git clone" not in text
        assert "versioned" not in text.lower() or "release" in text.lower()


import pytest


@pytest.mark.corpus
def test_display_recipe_executes_against_real_riao_edition(tmp_path: Path) -> None:
    from oracc_tf import corpus, loader, metadata, paths

    source = paths.DATA / "riao/ria1/corpusjson/Q001801.json"
    if not source.is_file():
        pytest.skip("RIAO Q001801 source member unavailable")
    tf_root = tmp_path / "tf"
    corpus.build_tf(
        tf_root,
        editions=[loader.load_edition(source)],
        metadata_index=metadata.MetadataIndex.empty(),
    )
    api = corpus.load_tf(tf_root)
    blocks = python_blocks(page("text-formats.md"))
    assert blocks
    env = {"api": api}
    exec(compile(blocks[0], "text-formats.md", "exec"), env)
    assert api.F.document_key.v(env["line"]) == "riao/ria1:Q001801"
    assert isinstance(env["cuneiform"], str)
    assert env["cuneiform"].strip()
    assert "𒂍" in env["cuneiform"]  # Q001801.1.1.0, source utf8
    assert any(
        api.F.utf8.v(sign) in env["cuneiform"]
        for sign in api.L.d(env["line"], otype="sign")
        if api.F.synthetic.v(sign) != 1 and api.F.utf8.v(sign)
    )
    assert isinstance(env["transliteration"], str)
    assert env["transliteration"].strip()
    assert "E₂" in env["transliteration"]  # Q001801.1.1 source form
    assert any(
        api.F.form.v(word) in env["transliteration"]
        for word in api.L.d(env["line"], otype="word")
        if api.F.form.v(word)
    )


def test_reference_landing_does_not_claim_unpublished_corpus_is_released() -> None:
    index = page("index.md")
    assert "for the released" not in index.lower()
    assert "pre-1.0" in index or "release candidate" in index
