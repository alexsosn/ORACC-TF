"""M9 regression gate for ADR-0001 synthetic TF-slot alignment."""

from __future__ import annotations

from pathlib import Path

from oracc_tf import corpus, loader, metadata
from oracc_tf.translations import TranslationUnit


def _word(text_id: str, suffix: str, form: str, utf8: str | None = None):
    features: dict[str, object] = {"form": form, "gdl": []}
    if utf8 is not None:
        features["gdl"] = [{"v": form, "utf8": utf8}]
    return {"node": "l", "id": f"{text_id}.{suffix}", "f": features}


def _edition(text_id: str, body: list[dict[str, object]]) -> loader.Edition:
    doc = {
        "type": "cdl",
        "textid": text_id,
        "cdl": [{
            "node": "c",
            "type": "text",
            "id": f"{text_id}.U0",
            "cdl": body,
        }],
    }
    word_count = sum(int(item.get("node") == "l") for item in body)
    return loader.Edition(
        subproject="test/unit",
        text_id=text_id,
        path=Path(f"/test/unit/corpusjson/{text_id}.json"),
        doc=doc,
        word_count=word_count,
    )


def _unit(edition: loader.Edition, line_ref: str, source_id: str) -> TranslationUnit:
    return TranslationUnit(
        document_key=edition.key,
        text_id=edition.text_id,
        source_id=source_id,
        subtype=None,
        sref=line_ref,
        eref=line_ref,
        rows=1,
        label=None,
        se_label=None,
        text="translation",
        text_raw="translation",
    )


def _slots(api, node: int) -> tuple[int, ...]:
    return tuple(api.L.d(node, otype="sign"))


def test_translation_of_signless_word_line_uses_only_its_synthetic_slot(tmp_path):
    edition = _edition("QTRWORD", [
        {"node": "d", "type": "surface", "ref": "", "label": "o"},
        {"node": "d", "type": "line-start", "ref": "QTRWORD.1", "label": "1"},
        _word("QTRWORD", "l1", "a", "𒀀"),
        {"node": "d", "type": "line-start", "ref": "QTRWORD.2", "label": "2"},
        _word("QTRWORD", "l2", "*"),
        {"node": "d", "type": "line-start", "ref": "QTRWORD.3", "label": "3"},
        _word("QTRWORD", "l3", "ba", "𒁀"),
    ])
    unit = _unit(edition, "QTRWORD.2", "QTRWORD.tr1")

    report = corpus.build_tf(
        tmp_path,
        editions=(edition,),
        metadata_index=metadata.MetadataIndex.empty(),
        translations_by_document={edition.key: (unit,)},
    )
    assert report.signs == 2
    assert report.synthetic_slots == 1
    assert report.tf_slots == 3
    assert report.translation_units == 1

    api = corpus.load_tf(tmp_path)
    node = next(iter(api.F.otype.s("translation_unit")))
    assert _slots(api, node) == (2,)
    assert api.F.synthetic.v(2) == 1
    assert api.F.utf8.v(1) == "𒀀"
    assert api.F.utf8.v(3) == "𒁀"
    assert 1 not in _slots(api, node)
    assert 3 not in _slots(api, node)


def test_translation_of_structurally_empty_line_uses_structural_anchor(tmp_path):
    edition = _edition("QTREMPTY", [
        {"node": "d", "type": "surface", "ref": "", "label": "o"},
        {"node": "d", "type": "line-start", "ref": "QTREMPTY.1", "label": "1"},
        _word("QTREMPTY", "l1", "a", "𒀀"),
        {"node": "d", "type": "line-start", "ref": "QTREMPTY.2", "label": "2"},
        {"node": "d", "type": "line-start", "ref": "QTREMPTY.3", "label": "3"},
        _word("QTREMPTY", "l3", "ba", "𒁀"),
    ])
    unit = _unit(edition, "QTREMPTY.2", "QTREMPTY.tr1")

    report = corpus.build_tf(
        tmp_path,
        editions=(edition,),
        metadata_index=metadata.MetadataIndex.empty(),
        translations_by_document={edition.key: (unit,)},
    )
    assert report.signs == 2
    assert report.synthetic_slots == 1
    assert report.translation_units == 1

    api = corpus.load_tf(tmp_path)
    lines = {
        api.F.source_id.v(node): node
        for node in api.F.otype.s("line")
    }
    translation = next(iter(api.F.otype.s("translation_unit")))
    assert _slots(api, lines["QTREMPTY.2"]) == (2,)
    assert _slots(api, translation) == (2,)
    assert api.F.synthetic.v(2) == 1
    assert api.F.utf8.v(2) is None
