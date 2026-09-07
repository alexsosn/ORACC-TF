"""Adversarial stability checks for the P-001 M9 translation layer."""

from __future__ import annotations

from pathlib import Path

import pytest

from oracc_tf import corpus, loader, metadata, translations


def _edition() -> loader.Edition:
    text_id = "QSTABLE"
    doc = {
        "type": "cdl",
        "textid": text_id,
        "cdl": [{
            "node": "c",
            "type": "text",
            "id": f"{text_id}.U0",
            "cdl": [
                {"node": "d", "type": "surface", "ref": "", "label": "o"},
                {"node": "d", "type": "line-start", "ref": f"{text_id}.1", "label": "1"},
                {"node": "l", "id": f"{text_id}.l1", "f": {"form": "a", "gdl": [{"v": "a", "utf8": "𒀀"}]}},
            ],
        }],
    }
    return loader.Edition(
        subproject="test/unit",
        text_id=text_id,
        path=Path("/test/unit/corpusjson/QSTABLE.json"),
        doc=doc,
        word_count=1,
    )


def _unit(*, document_key: str = "test/unit:QSTABLE") -> translations.TranslationUnit:
    return translations.TranslationUnit(
        document_key=document_key,
        text_id=document_key.rsplit(":", 1)[-1],
        source_id="QSTABLE_project-en.0",
        subtype="tr",
        sref="QSTABLE.1",
        eref="QSTABLE.1",
        rows=1,
        label=None,
        se_label=None,
        text="translation",
        text_raw="translation",
        source_name="tei.zip",
        source_sha256="b" * 64,
    )


def _build(path: Path, *, with_translation: bool) -> corpus.CorpusBuildReport:
    edition = _edition()
    kwargs = {}
    if with_translation:
        kwargs["translations_by_document"] = {edition.key: (_unit(),)}
    return corpus.build_tf(
        path,
        editions=(edition,),
        metadata_index=metadata.MetadataIndex.empty(),
        **kwargs,
    )


def test_translation_build_is_byte_deterministic(tmp_path):
    left = tmp_path / "left"
    right = tmp_path / "right"
    _build(left, with_translation=True)
    _build(right, with_translation=True)

    left_files = {path.name: path.read_bytes() for path in left.glob("*.tf")}
    right_files = {path.name: path.read_bytes() for path in right.glob("*.tf")}
    assert left_files
    assert left_files == right_files


def test_rebuild_without_translations_removes_stale_translation_schema(tmp_path):
    out = tmp_path / "tf"
    translated = _build(out, with_translation=True)
    assert translated.translation_units == 1
    assert (out / "translation_text.tf").is_file()

    plain = _build(out, with_translation=False)
    assert plain.translation_source_supplied is False
    assert plain.translation_units == 0
    assert not (out / "translation_text.tf").exists()
    assert not (out / "translation_document.tf").exists()

    api = corpus.load_tf(out)
    assert not api.F.otype.s("translation_unit")
    assert not hasattr(api.F, "translation_text")


def test_translation_index_rejects_documents_outside_build(tmp_path):
    edition = _edition()
    foreign = translations.TranslationUnit(
        document_key="test/unit:QFOREIGN",
        text_id="QFOREIGN",
        source_id="QFOREIGN_project-en.0",
        subtype="tr",
        sref="QFOREIGN.1",
        eref="QFOREIGN.1",
        rows=1,
        label=None,
        se_label=None,
        text="foreign",
        text_raw="foreign",
    )

    with pytest.raises(corpus.CorpusBuildError, match="absent from build"):
        corpus.build_tf(
            tmp_path,
            editions=(edition,),
            metadata_index=metadata.MetadataIndex.empty(),
            translations_by_document={"test/unit:QFOREIGN": (foreign,)},
        )
