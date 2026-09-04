"""P-001 M6 - joined whole-corpus invariants and Text-Fabric warp load.

Acceptance criteria from P-001 §5 M6:
- 320,975 source words; 2,078 parseable documents / 1,845 populated / 233 stubs;
- composite document keys are unique;
- every sign belongs to exactly one word and every word to exactly one line;
- every populated document has a valid document/face/line section path;
- the M1 sign count stays pinned and Unicode coverage is frozen here;
- generated ``otype``/``oslots`` load cleanly in Text-Fabric.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from oracc_tf import corpus, loader, metadata, paths


def _edition(subproject: str, text_id: str, *, signless: bool = False) -> loader.Edition:
    words = []
    if signless:
        words.append({
            "node": "l",
            "id": f"{text_id}.l0",
            "f": {"form": "*", "gdl": []},
        })
    words.append({
        "node": "l",
        "id": f"{text_id}.l1",
        "f": {"form": "a", "gdl": [{"v": "a", "utf8": "𒀀"}]},
    })
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
                *words,
            ],
        }],
    }
    return loader.Edition(
        subproject=subproject,
        text_id=text_id,
        path=Path(f"/{subproject}/corpusjson/{text_id}.json"),
        doc=doc,
        word_count=len(words),
    )


def test_slotless_source_word_survives_tf_and_keeps_explicit_line_edge(tmp_path):
    edition = _edition("test/unit", "QTEST", signless=True)
    report = corpus.build_tf(
        tmp_path,
        editions=(edition,),
        metadata_index=metadata.MetadataIndex.empty(),
    )

    assert report.documents == 1
    assert report.populated_documents == 1
    assert report.words == 2
    assert report.signs == 1
    assert report.slotless_words == 1
    assert report.sign_word_membership_errors == 0
    assert report.word_line_membership_errors == 0
    assert report.section_path_errors == 0

    api = corpus.load_tf(tmp_path)
    word_nodes = api.F.otype.s("word")
    by_source = {api.F.source_id.v(node): node for node in word_nodes}

    assert set(by_source) == {"QTEST.l0", "QTEST.l1"}
    assert tuple(api.E.oslots.s(by_source["QTEST.l0"])) == ()
    assert len(api.E.word_line.s(by_source["QTEST.l0"])) == 1
    assert api.T.sectionFromNode(1) == (
        "test/unit:QTEST",
        "QTEST.face.1",
        "QTEST.1",
    )


def test_same_q_number_in_two_subprojects_stays_two_documents(tmp_path):
    editions = (
        _edition("test/a", "QDUPE"),
        _edition("test/b", "QDUPE"),
    )
    report = corpus.build_tf(
        tmp_path,
        editions=editions,
        metadata_index=metadata.MetadataIndex.empty(),
    )

    assert report.documents == 2
    assert report.unique_document_keys == 2
    assert report.document_key_collisions == 0

    api = corpus.load_tf(tmp_path)
    document_nodes = api.F.otype.s("document")
    assert {api.F.document.v(node) for node in document_nodes} == {
        "test/a:QDUPE",
        "test/b:QDUPE",
    }


@pytest.mark.corpus
def test_joined_corpus_invariants_and_tf_warp_load(tmp_path):
    report = corpus.build_full_tf(tmp_path, data=paths.DATA)

    assert report.documents == 2078
    assert report.populated_documents == 1845
    assert report.stub_documents == 233
    assert report.unique_document_keys == report.documents
    assert report.document_key_collisions == 0

    assert report.words == 320975
    assert report.signs == 792651
    assert report.slotless_words == 295
    assert report.sign_word_membership_errors == 0
    assert report.word_line_membership_errors == 0
    assert report.section_path_errors == 0

    # Diagnostic first freeze: implementation must report the measured exact
    # count, then this deliberate RED assertion is replaced with that value.
    assert report.unicode_signs == 0, report.report()

    api = corpus.load_tf(tmp_path)
    assert api.F.otype.maxSlot == 792651
    assert len(api.F.otype.s("document")) == 2078
    assert len(api.F.otype.s("word")) == 320975
    assert len(api.F.otype.s("line")) == 56226
    assert len(api.F.otype.s("lex")) == 8025
