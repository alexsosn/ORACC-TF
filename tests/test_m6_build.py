"""P-001 M6 integrated graph and Text-Fabric warp acceptance tests.

M0-M5 deliberately validate source layers independently. M6 is where those
layers must agree as one graph: signs are the only slots; every sign is owned
by exactly one word; every word belongs to exactly one line; document identity
is subproject-qualified; and the resulting warp must be loadable by
Text-Fabric without deleting zero-sign words or metadata-only stubs.
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
    assert graph.max_slot == sum(word.sign_count for word in graph.words.values())
    assert graph.max_slot > 0
    assert set(graph.sign_owner) == set(range(1, graph.max_slot + 1))
    assert all(owner in graph.words for owner in graph.sign_owner.values())

    for word_id, word in graph.words.items():
        assert graph.word_to_line[word_id]
        assert graph.node_slots[word_id] == tuple(word.slot_ids)


def test_stub_document_survives_as_a_real_no_slot_node():
    edition = loader.load_edition(Q000000)
    graph = build.build_editions((edition,))

    assert edition.populated is False
    assert graph.document_nodes[edition.key].populated == 0
    assert graph.node_slots[edition.key] == ()
    assert graph.words == {}
    assert graph.max_slot == 0


def test_text_fabric_warp_round_trips_fixture_and_no_slot_stub(tmp_path):
    pytest.importorskip("tf.fabric", reason="M6 requires the Text-Fabric runtime")
    from tf.fabric import Fabric

    editions = (loader.load_edition(Q005620), loader.load_edition(Q000000))
    out = tmp_path / "tf"
    result = build.export_tf_editions(editions, out)

    assert result.good is True
    TF = Fabric(locations=str(out), modules=[""], silent="deep")
    api = TF.load("otype oslots source_id document_key populated", silent="deep")
    assert api is not None
    assert api.F.otype.slotType == "sign"
    assert api.F.otype.maxSlot == result.graph.max_slot

    documents = api.F.otype.s("document")
    by_key = {api.F.document_key.v(n): n for n in documents}
    assert set(by_key) == {"riao/ria1:Q005620", "riao/ria4:Q000000"}
    assert api.E.oslots.s(by_key["riao/ria4:Q000000"]) == ()
    assert api.F.populated.v(by_key["riao/ria4:Q000000"]) == 0


@pytest.mark.corpus
def test_whole_corpus_integrated_invariants_are_pinned():
    result = build.census(paths.DATA)

    assert result.documents == 2078
    assert result.populated_documents == 1845
    assert result.stub_documents == 233
    assert result.duplicate_document_keys == 0
    assert result.signs == 792651
    assert result.words == 320975
    assert result.lines == 56226
    assert result.lexemes == 8025
    assert result.sign_owner_errors == 0, result.report()
    assert result.word_line_errors == 0, result.report()
    assert result.populated_section_path_errors == 0, result.report()
    assert result.non_unicode_non_x_signs == 0, result.report()
    assert result.unicode_signs + result.non_unicode_signs == result.signs


@pytest.mark.corpus
def test_whole_corpus_otype_and_oslots_load_cleanly_in_text_fabric(tmp_path):
    pytest.importorskip("tf.fabric", reason="M6 requires the Text-Fabric runtime")
    from tf.fabric import Fabric

    out = tmp_path / "tf"
    result = build.export_tf(paths.DATA, out)
    assert result.good is True, result.census.report()

    TF = Fabric(locations=str(out), modules=[""], silent="deep")
    api = TF.load("otype oslots document_key source_id populated", silent="deep")
    assert api is not None
    assert api.F.otype.slotType == "sign"
    assert api.F.otype.maxSlot == 792651
    assert len(api.F.otype.s("document")) == 2078
    assert len(api.F.otype.s("word")) == 320975
    assert len(api.F.otype.s("line")) == 56226
    assert len(api.F.otype.s("lex")) == 8025

    # Metadata-only stubs and M2 zero-sign words are part of the graph even
    # though they have no slots. Their survival is a source-preservation
    # invariant, not something to repair by inventing textual positions.
    stub_nodes = [
        n for n in api.F.otype.s("document") if api.F.populated.v(n) == 0
    ]
    assert len(stub_nodes) == 233
    assert all(api.E.oslots.s(n) == () for n in stub_nodes)
