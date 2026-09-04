"""P-001 M8 — cross-validation against Nino-cunei/oldbabylonian 1.0.6.

Pinned upstream contract (archived repository, tf/1.0.6):
- ``readingu`` is a string feature on sign slots containing cuneiform Unicode;
- ``lnno`` is a string feature on line nodes containing the ATF line number/label;
- ``period`` and ``genre`` are string document metadata features.

M8 does not require the two corpora to share identical vocabularies. It requires
that shared feature names mean the same kind of thing and inhabit compatible
value domains.
"""

from __future__ import annotations

from pathlib import Path

from oracc_tf import corpus, loader, metadata


def _edition() -> loader.Edition:
    text_id = "QTEST"
    doc = {
        "type": "cdl",
        "textid": text_id,
        "cdl": [{
            "node": "c",
            "type": "text",
            "id": f"{text_id}.U0",
            "cdl": [
                {"node": "d", "type": "surface", "ref": "", "label": ""},
                {
                    "node": "d",
                    "type": "line-start",
                    "ref": f"{text_id}.1",
                    "label": "1",
                },
                {
                    "node": "l",
                    "id": f"{text_id}.l1",
                    "f": {"form": "a", "gdl": [{"v": "a", "utf8": "𒀀"}]},
                },
            ],
        }],
    }
    return loader.Edition(
        subproject="test/unit",
        text_id=text_id,
        path=Path("/test/unit/corpusjson/QTEST.json"),
        doc=doc,
        word_count=1,
    )


def _metadata() -> metadata.MetadataIndex:
    return metadata.MetadataIndex(records={
        "test/unit:QTEST": {
            "period": "Old Babylonian (ca. 1900-1600 BC)",
            "genre": "Letter",
        }
    })


def test_generated_tf_exposes_oldbabylonian_shared_feature_names(tmp_path):
    corpus.build_tf(tmp_path, editions=(_edition(),), metadata_index=_metadata())
    api = corpus.load_tf(tmp_path)

    sign = api.F.otype.s("sign")[0]
    line = api.F.otype.s("line")[0]
    document = api.F.otype.s("document")[0]

    assert api.F.readingu.v(sign) == "𒀀"
    assert api.F.lnno.v(line) == "1"
    assert api.F.period.v(document) == "Old Babylonian (ca. 1900-1600 BC)"
    assert api.F.genre.v(document) == "Letter"


def test_oldbabylonian_aliases_preserve_existing_oracc_tf_values(tmp_path):
    corpus.build_tf(tmp_path, editions=(_edition(),), metadata_index=_metadata())
    api = corpus.load_tf(tmp_path)

    sign = api.F.otype.s("sign")[0]
    line = api.F.otype.s("line")[0]

    # Compatibility aliases must not replace or reinterpret the source-facing
    # ORACC-TF features introduced in earlier milestones.
    assert api.F.readingu.v(sign) == api.F.utf8.v(sign)
    assert api.F.lnno.v(line) == api.F.label.v(line)


def test_shared_feature_metadata_are_string_domains(tmp_path):
    corpus.build_tf(tmp_path, editions=(_edition(),), metadata_index=_metadata())
    api = corpus.load_tf(tmp_path)

    for feature in ("readingu", "lnno", "period", "genre"):
        assert api.Fs(feature).meta["valueType"] == "str"
