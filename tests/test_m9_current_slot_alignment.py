"""Current-architecture RED gate for translation alignment over synthetic TF slots."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from oracc_tf import corpus, loader, metadata


@dataclass(frozen=True)
class _Unit:
    document_key: str
    text_id: str
    source_id: str
    sref: str
    eref: str
    subtype: str | None = None
    rows: int = 1
    label: str | None = None
    se_label: str | None = None
    text: str = "translation"
    text_raw: str = "translation"
    notes: tuple[object, ...] = ()
    source_name: str | None = None
    source_sha256: str | None = None
    source_url: str | None = None
    source_license: str | None = None
    source_license_url: str | None = None


def _word(text_id: str, suffix: str, form: str, utf8: str | None = None):
    features: dict[str, object] = {"form": form, "gdl": []}
    if utf8 is not None:
        features["gdl"] = [{"v": form, "utf8": utf8}]
    return {"node": "l", "id": f"{text_id}.{suffix}", "f": features}


def _edition(text_id: str, body: list[dict[str, object]]) -> loader.Edition:
    doc = {
        "type": "cdl",
        "textid": text_id,
        "cdl": [{"node": "c", "type": "text", "id": f"{text_id}.U0", "cdl": body}],
    }
    return loader.Edition(
        subproject="test/translation",
        text_id=text_id,
        path=Path(f"/test/translation/corpusjson/{text_id}.json"),
        doc=doc,
        word_count=sum(int(item.get("node") == "l") for item in body),
    )


def test_translation_range_uses_signless_lines_synthetic_slot_without_neighbour_borrowing(tmp_path):
    edition = _edition("QTRRED", [
        {"node": "d", "type": "surface", "ref": "", "label": "o"},
        {"node": "d", "type": "line-start", "ref": "QTRRED.1", "label": "1"},
        _word("QTRRED", "l1", "a", "𒀀"),
        {"node": "d", "type": "line-start", "ref": "QTRRED.2", "label": "2"},
        _word("QTRRED", "l2", "*"),
        {"node": "d", "type": "line-start", "ref": "QTRRED.3", "label": "3"},
        _word("QTRRED", "l3", "ba", "𒁀"),
    ])
    unit = _Unit(
        document_key=edition.key,
        text_id=edition.text_id,
        source_id="QTRRED.tr1",
        sref="QTRRED.2",
        eref="QTRRED.2",
        notes=("Editorial note",),
    )
    dollar_unit = _Unit(
        document_key=edition.key,
        text_id=edition.text_id,
        source_id="QTRRED.dollar1",
        sref="QTRRED.2",
        eref="QTRRED.2",
        subtype="dollar",
        text="",
        text_raw="",
    )

    report = corpus.build_tf(
        tmp_path,
        editions=(edition,),
        metadata_index=metadata.MetadataIndex.empty(),
        translations_by_document={edition.key: (unit, dollar_unit)},
    )

    assert report.signs == 2
    assert report.synthetic_slots == 1
    assert report.translation_units == 2

    api = corpus.load_tf(tmp_path)
    translation = next(iter(api.F.otype.s("translation_unit")))
    slots = tuple(api.L.d(translation, otype="sign"))
    assert slots == (2,)
    assert api.F.translation_id.v(translation) == f"{edition.key}:QTRRED.tr1"
    assert api.F.synthetic.v(2) == 1
    assert api.F.utf8.v(1) == "𒀀"
    assert api.F.utf8.v(3) == "𒁀"
    line_two = next(node for node in api.F.line.s("QTRRED.2"))
    assert translation in api.E.translation_line.t(line_two)
    assert any(
        api.F.translation_subtype.v(node) == "dollar"
        for node in api.F.otype.s("translation_unit")
    )
    note = next(iter(api.F.otype.s("translation_note")))
    assert api.F.translation_note_text.v(note) == "Editorial note"
    assert tuple(api.L.d(note, otype="sign")) == slots
    assert api.E.translation_note_unit.f(note) == (translation,)


def test_translation_units_without_source_alignment_are_reported_as_gaps(tmp_path):
    edition = _edition("QTRGAP", [
        {"node": "d", "type": "surface", "ref": "", "label": "o"},
        {"node": "d", "type": "line-start", "ref": "QTRGAP.1", "label": "1"},
        _word("QTRGAP", "l1", "a", "𒀀"),
    ])
    unaligned = _Unit(
        document_key=edition.key,
        text_id=edition.text_id,
        source_id="QTRGAP.tr-missing",
        sref=None,
        eref=None,
    )
    missing_line = _Unit(
        document_key=edition.key,
        text_id=edition.text_id,
        source_id="QTRGAP.tr-unresolved",
        sref="QTRGAP.99",
        eref="QTRGAP.99",
    )

    report = corpus.build_tf(
        tmp_path,
        editions=(edition,),
        metadata_index=metadata.MetadataIndex.empty(),
        translations_by_document={edition.key: (unaligned, missing_line)},
    )

    assert report.translation_units == 0
    assert report.translation_gaps == 2
    assert any("source provides no line range" in gap for gap in report.translation_gap_details)
    assert any("unresolved source line range" in gap for gap in report.translation_gap_details)


def test_generated_translation_identity_is_not_mislabeled_as_source_id(tmp_path):
    edition = _edition("QTRSOURCE", [
        {"node": "d", "type": "surface", "ref": "", "label": "o"},
        {"node": "d", "type": "line-start", "ref": "QTRSOURCE.1", "label": "1"},
        _word("QTRSOURCE", "l1", "a", "𒀀"),
    ])
    unit = _Unit(
        document_key=edition.key,
        text_id=edition.text_id,
        source_id=None,
        sref="QTRSOURCE.1",
        eref="QTRSOURCE.1",
    )

    corpus.build_tf(
        tmp_path,
        editions=(edition,),
        metadata_index=metadata.MetadataIndex.empty(),
        translations_by_document={edition.key: (unit,)},
    )

    api = corpus.load_tf(tmp_path)
    node = next(iter(api.F.otype.s("translation_unit")))
    assert api.F.translation_id.v(node) == f"{edition.key}:QTRSOURCE.tr1"
    assert api.F.translation_source_id.v(node) is None
