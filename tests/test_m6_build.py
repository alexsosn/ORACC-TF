"""P-001 M6 integrated graph and Text-Fabric warp acceptance tests.

M0-M5 deliberately validate source layers independently. M6 is where those
layers must agree as one graph: source signs remain the semantic sign census;
every source sign is owned by exactly one word; every word belongs to exactly
one line; document identity is subproject-qualified; and the resulting warp
must be loadable by Text-Fabric without deleting zero-sign words or
metadata-only stubs.

Text-Fabric cannot serialise an unlinked non-slot node. The source model keeps
zero-sign words and stubs at empty spans, but the TF projection therefore uses
explicit synthetic anchor slots. Anchors are infrastructure, never source
signs: they carry ``synthetic=1`` and ``slot_kind=anchor`` and are counted
separately from the pinned 792,651 semantic source signs.
"""

from __future__ import annotations

import pytest

from oracc_tf import build, loader, paths


Q005620 = paths.DATA / "riao/ria1/corpusjson/Q005620.json"
Q000000 = paths.DATA / "riao/ria4/corpusjson/Q000000.json"


def test_fixture_graph_uses_sign_slots_and_preserves_document_identity():
    edition = loader.load_edition(Q005620)
    graph = build.build_editions((edition,))

    assert graph.slot_type == "sign"
    assert tuple(graph.document_nodes) == ("riao/ria1:Q005620",)
    assert graph.source_sign_count == sum(word.sign_count for word in graph.words.values())
    assert graph.source_sign_count > 0
    assert set(graph.sign_owner) == set(graph.signs)
    assert all(owner in graph.words for owner in graph.sign_owner.values())

    for word_id, word in graph.words.items():
        assert graph.word_to_line[word_id]
        if word.sign_count:
            assert len(graph.node_slots[word_id]) == word.sign_count
        else:
            assert len(graph.node_slots[word_id]) == 1
            anchor = graph.node_slots[word_id][0]
            assert graph.anchor_owner[anchor] == word_id


def test_stub_document_uses_one_explicit_synthetic_anchor_in_tf_projection():
    edition = loader.load_edition(Q000000)
    graph = build.build_editions((edition,))

    assert edition.populated is False
    assert graph.document_nodes[edition.key].populated == 0
    assert graph.words == {}
    assert graph.source_sign_count == 0
    assert len(graph.node_slots[edition.key]) == 1
    anchor = graph.node_slots[edition.key][0]
    assert graph.anchor_owner[anchor] == edition.key
    assert graph.max_slot == 1


def test_text_fabric_warp_round_trips_fixture_and_stub_anchor(tmp_path):
    pytest.importorskip("tf.fabric", reason="M6 requires the Text-Fabric runtime")
    from tf.fabric import Fabric

    editions = (loader.load_edition(Q005620), loader.load_edition(Q000000))
    out = tmp_path / "tf"
    result = build.export_tf_editions(editions, out)

    assert result.good is True
    TF = Fabric(locations=str(out), modules=[""], silent="deep")
    api = TF.load(
        "otype oslots source_id document_key populated synthetic slot_kind anchor_reason",
        silent="deep",
    )
    assert api is not None and api is not False
    assert api.F.otype.slotType == "sign"
    assert api.F.otype.maxSlot == result.graph.max_slot

    documents = api.F.otype.s("document")
    by_key = {api.F.document_key.v(n): n for n in documents}
    assert set(by_key) == {"riao/ria1:Q005620", "riao/ria4:Q000000"}
    stub = by_key["riao/ria4:Q000000"]
    stub_slots = api.E.oslots.s(stub)
    assert len(stub_slots) == 1
    anchor = stub_slots[0]
    assert api.F.synthetic.v(anchor) == 1
    assert api.F.slot_kind.v(anchor) == "anchor"
    assert api.F.anchor_reason.v(anchor) == "stub_document"
    assert api.F.populated.v(stub) == 0


@pytest.mark.corpus
def test_whole_corpus_integrated_invariants_are_pinned():
    result = build.census(paths.DATA)

    assert result.documents == 2078
    assert result.populated_documents == 1845
    assert result.stub_documents == 233
    assert result.duplicate_document_keys == 0
    assert result.source_signs == 792651
    assert result.words == 320975
    assert result.lines == 56226
    assert result.lexemes == 8025
    assert result.synthetic_anchor_slots >= 295 + 233
    assert result.tf_slots == result.source_signs + result.synthetic_anchor_slots
    assert result.sign_owner_errors == 0, result.report()
    assert result.anchor_owner_errors == 0, result.report()
    assert result.word_line_errors == 0, result.report()
    assert result.populated_section_path_errors == 0, result.report()
    assert result.non_unicode_non_x_signs == 0, result.report()
    assert result.unicode_signs + result.non_unicode_source_signs == result.source_signs


@pytest.mark.corpus
def test_whole_corpus_otype_and_oslots_load_cleanly_in_text_fabric(tmp_path):
    pytest.importorskip("tf.fabric", reason="M6 requires the Text-Fabric runtime")
    from tf.fabric import Fabric

    out = tmp_path / "tf"
    result = build.export_tf(paths.DATA, out)
    assert result.good is True, result.census.report()

    TF = Fabric(locations=str(out), modules=[""], silent="deep")
    api = TF.load(
        "otype oslots document_key source_id populated synthetic slot_kind anchor_reason",
        silent="deep",
    )
    assert api is not None and api is not False
    assert api.F.otype.slotType == "sign"
    assert api.F.otype.maxSlot == result.census.tf_slots
    assert len(api.F.otype.s("document")) == 2078
    assert len(api.F.otype.s("word")) == 320975
    assert len(api.F.otype.s("line")) == 56226
    assert len(api.F.otype.s("lex")) == 8025

    stub_nodes = [
        n for n in api.F.otype.s("document") if api.F.populated.v(n) == 0
    ]
    assert len(stub_nodes) == 233
    assert all(len(api.E.oslots.s(n)) >= 1 for n in stub_nodes)
    assert sum(api.F.synthetic.v(s) == 1 for s in api.F.otype.s("sign")) == result.census.synthetic_anchor_slots
