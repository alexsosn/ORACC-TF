"""Issue #72 RED contracts for source-faithful Text-Fabric display formats."""

from __future__ import annotations

from pathlib import Path

from tf.app import use

from oracc_tf import corpus, loader, metadata, paths


def _word(text_id: str, suffix: str, form: str, signs: list[tuple[str, str | None]], **features):
    gdl = []
    for i, (value, utf8) in enumerate(signs):
        item: dict[str, object] = {"v": value, "id": f"{text_id}.{suffix}.{i}"}
        if utf8 is not None:
            item["utf8"] = utf8
        gdl.append(item)
    f: dict[str, object] = {"form": form, "gdl": gdl, **features}
    return {"node": "l", "id": f"{text_id}.{suffix}", "f": f}


def _edition(text_id: str, source_words: list[dict[str, object]]) -> loader.Edition:
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
    return loader.Edition(
        subproject="test/display",
        text_id=text_id,
        path=Path(f"/test/display/corpusjson/{text_id}.json"),
        doc=doc,
        word_count=len(source_words),
    )


def _build(tmp_path: Path, edition: loader.Edition):
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


def test_named_formats_render_multisign_word_once_at_correct_levels(tmp_path: Path) -> None:
    edition = _edition(
        "QFMT",
        [_word("QFMT", "l1", "ma-an", [("ma", "𒈠"), ("an", "𒀭")])],
    )
    api = _build(tmp_path, edition)
    word = _node_by_source(api, "word", "QFMT.l1")

    assert api.T.formats["text-orig-full"] == "sign"
    assert api.T.formats["text-trans-full"] == "word"
    assert api.T.text(word, fmt="text-orig-full") == "𒈠𒀭 "
    assert api.T.text(word, fmt="text-trans-full") == "ma-an "


def test_cuneiform_trailer_marks_only_final_real_sign_of_each_word(tmp_path: Path) -> None:
    edition = _edition(
        "QBOUND",
        [
            _word("QBOUND", "l1", "a-ba", [("a", "𒀀"), ("ba", "𒁀")]),
            _word("QBOUND", "l2", "mnn", []),
            _word("QBOUND", "l3", "e", [("e", "𒂊")]),
        ],
    )
    api = _build(tmp_path, edition)
    line = _node_by_source(api, "line", "QBOUND.1")
    words = {
        source_id: _node_by_source(api, "word", source_id)
        for source_id in ("QBOUND.l1", "QBOUND.l2", "QBOUND.l3")
    }

    assert api.T.text(line, fmt="text-orig-full") == "𒀀𒁀 𒂊 "
    assert api.T.text(line, fmt="text-trans-full") == "a-ba mnn e "

    first_slots = tuple(api.L.d(words["QBOUND.l1"], otype="sign"))
    zero_slots = tuple(api.L.d(words["QBOUND.l2"], otype="sign"))
    last_slots = tuple(api.L.d(words["QBOUND.l3"], otype="sign"))
    assert [api.F.cuneiform_trailer.v(slot) for slot in first_slots] == [None, " "]
    assert len(zero_slots) == 1 and api.F.synthetic.v(zero_slots[0]) == 1
    assert api.F.cuneiform_trailer.v(zero_slots[0]) is None
    assert [api.F.cuneiform_trailer.v(slot) for slot in last_slots] == [" "]


def test_synthetic_anchor_is_empty_but_zero_sign_source_form_survives(tmp_path: Path) -> None:
    edition = _edition(
        "QZERO",
        [
            _word("QZERO", "l1", "mnn", [], lang="arc"),
            _word("QZERO", "l2", "x", [("x", None)]),
        ],
    )
    api = _build(tmp_path, edition)
    line = _node_by_source(api, "line", "QZERO.1")
    zero_word = _node_by_source(api, "word", "QZERO.l1")
    synthetic = tuple(api.L.d(zero_word, otype="sign"))[0]

    assert api.F.synthetic.v(synthetic) == 1
    assert api.T.text(synthetic, fmt="text-orig-full") == ""
    assert api.T.text(synthetic, fmt="text-trans-full") == ""
    assert api.T.text(zero_word, fmt="text-orig-full") == ""
    assert api.T.text(zero_word, fmt="text-trans-full") == "mnn "
    # Missing Unicode is not replaced by guessed cuneiform; source x remains in transliteration.
    assert api.T.text(line, fmt="text-orig-full") == " "
    assert api.T.text(line, fmt="text-trans-full") == "mnn x "


def test_composite_numeral_uses_source_slot_not_rendering_reference(tmp_path: Path) -> None:
    edition = loader.load_edition(paths.DATA / "riao/ria1/corpusjson/Q005620.json")
    api = _build(tmp_path, edition)
    word = _node_by_source(api, "word", "Q005620.l009d1")
    rendered = api.T.text(word, fmt="text-orig-full")

    assert rendered == "𒁹 "
    assert rendered.count("𒁹") == 1
    assert "1" not in rendered


def test_lex_default_distinguishes_citation_form_and_guide_word(tmp_path: Path) -> None:
    edition = _edition(
        "QLEXFMT",
        [
            _word(
                "QLEXFMT",
                "l1",
                "šarru",
                [("LUGAL", "𒈗")],
                lang="akk",
                cf="šarru",
                gw="king",
                pos="N",
                sig="@test/display%akk:šarru=šarru[king]N$šarru",
            )
        ],
    )
    api = _build(tmp_path, edition)
    lex = next(iter(api.F.otype.s("lex")))

    assert api.T.formats["lex-default"] == "lex"
    assert api.T.text(lex) == "šarru [king]"
    assert "@test/display" not in api.T.text(lex)


def test_format_metadata_and_presentation_feature_are_byte_deterministic(tmp_path: Path) -> None:
    edition = _edition(
        "QDET72",
        [
            _word("QDET72", "l1", "a-ba", [("a", "𒀀"), ("ba", "𒁀")]),
            _word("QDET72", "l2", "mnn", []),
        ],
    )
    left = tmp_path / "left"
    right = tmp_path / "right"
    _build(left, edition)
    _build(right, edition)

    for filename in ("otext.tf", "cuneiform_trailer.tf"):
        assert (left / filename).read_bytes() == (right / filename).read_bytes()


def test_advanced_app_observes_same_named_format_output(tmp_path: Path) -> None:
    edition = _edition(
        "QAPP72",
        [_word("QAPP72", "l1", "a-ba", [("a", "𒀀"), ("ba", "𒁀")])],
    )
    low = _build(tmp_path, edition)
    line = _node_by_source(low, "line", "QAPP72.1")
    expected_orig = low.T.text(line, fmt="text-orig-full")
    expected_trans = low.T.text(line, fmt="text-trans-full")

    app = use(f"data:{tmp_path.resolve()}", silent="deep")
    assert app is not None and app.api is not None
    assert app.api.T.text(line, fmt="text-orig-full") == expected_orig == "𒀀𒁀 "
    assert app.api.T.text(line, fmt="text-trans-full") == expected_trans == "a-ba "
