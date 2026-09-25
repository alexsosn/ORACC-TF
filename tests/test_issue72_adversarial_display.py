"""Independent adversarial contracts for issue #72 display semantics."""

from __future__ import annotations

from pathlib import Path

from oracc_tf import corpus, loader, metadata


def _build(tmp_path: Path, text_id: str, source_words: list[dict[str, object]]):
    doc = {
        "type": "cdl",
        "textid": text_id,
        "cdl": [
            {
                "node": "c",
                "type": "text",
                "id": f"{text_id}.U0",
                "cdl": [
                    {"node": "d", "type": "surface", "ref": "", "label": "o"},
                    {
                        "node": "d",
                        "type": "line-start",
                        "ref": f"{text_id}.1",
                        "label": "1",
                    },
                    *source_words,
                ],
            }
        ],
    }
    edition = loader.Edition(
        subproject="test/adversarial-display",
        text_id=text_id,
        path=Path(f"/test/adversarial-display/corpusjson/{text_id}.json"),
        doc=doc,
        word_count=len(source_words),
    )
    corpus.build_tf(
        tmp_path,
        editions=(edition,),
        metadata_index=metadata.MetadataIndex.empty(),
    )
    return corpus.load_tf(tmp_path)


def _node_by_source(api, otype: str, source_id: str) -> int:
    return next(
        node
        for node in api.F.otype.s(otype)
        if api.F.source_id.v(node) == source_id
    )


def test_source_determinative_wrapper_renders_each_semantic_sign_once(tmp_path: Path) -> None:
    # Source-derived from RIAO Q005620.l00998 ({m}DINGIR-šu-ma). The
    # determinative wrapper is structural; its m child is a semantic slot.
    source_word = {
        "node": "l",
        "id": "Q005620.l00998",
        "frag": "{m}DINGIR-šu-ma",
        "ref": "Q005620.1.1",
        "f": {
            "lang": "akk",
            "form": "{m}DINGIR-šu-ma",
            "gdl": [
                {
                    "gg": "logo",
                    "gdl_type": "logo",
                    "group": [
                        {
                            "det": "semantic",
                            "pos": "pre",
                            "seq": [
                                {
                                    "v": "m",
                                    "utf8": "𒁹",
                                    "id": "Q005620.1.1.0",
                                }
                            ],
                        },
                        {
                            "s": "DINGIR",
                            "utf8": "𒀭",
                            "id": "Q005620.1.1.1",
                            "role": "logo",
                            "logolang": "sux",
                            "delim": "-",
                        },
                    ],
                },
                {
                    "v": "šu",
                    "utf8": "𒋗",
                    "id": "Q005620.1.1.2",
                    "delim": "-",
                },
                {"v": "ma", "utf8": "𒈠", "id": "Q005620.1.1.3"},
            ],
        },
    }
    api = _build(tmp_path, "Q005620", [source_word])
    word = _node_by_source(api, "word", "Q005620.l00998")

    rendered = api.T.text(word, fmt="text-orig-full")
    assert rendered == "𒁹𒀭𒋗𒈠 "
    assert len(tuple(api.L.d(word, otype="sign"))) == 4
    assert rendered.count("𒁹") == 1
    assert rendered.count("𒀭") == 1


def test_multi_lexeme_signature_keeps_canonical_labels_distinct(tmp_path: Path) -> None:
    # A multi-analysis ORACC signature is top-level source data, not an f-field.
    # Display must be derived from each canonical (cf, gw) lexeme, never the raw sig.
    source_word = {
        "node": "l",
        "id": "QMULTI.l1",
        "sig": (
            "@test/adversarial-display%akk:x=šarru[king]N$šarru"
            "&&@test/adversarial-display%akk:x=bēlu[lord]N$bēlu"
        ),
        "f": {
            "lang": "akk",
            "form": "x",
            "gdl": [{"v": "x", "id": "QMULTI.1.1.0"}],
        },
    }
    api = _build(tmp_path, "QMULTI", [source_word])
    labels = {api.T.text(lex) for lex in api.F.otype.s("lex")}

    assert labels == {"šarru [king]", "bēlu [lord]"}
    assert all("@test/" not in label and "&&" not in label for label in labels)
