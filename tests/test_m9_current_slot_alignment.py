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
    )

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
    translation = next(iter(api.F.otype.s("translation_unit")))
    slots = tuple(api.L.d(translation, otype="sign"))
    assert slots == (2,)
    assert api.F.synthetic.v(2) == 1
    assert api.F.utf8.v(1) == "𒀀"
    assert api.F.utf8.v(3) == "𒁀"
