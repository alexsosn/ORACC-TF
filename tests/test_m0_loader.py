"""P-001 M0 - harness and cardinalities.

Spec: docs/plans/P-001-riao-rinap-tf.md section 5, M0.

  Red:  assert the loader reports 2,081 files / 2,078 parseable / 1,845
        populated / 233 stubs; zero-byte files raise a typed EmptySourceError.
  Exit: all four cardinalities are computed and reported separately.

The four counts are separate on purpose. P-001 section 2.1 records that
revision 1 of the plan said "2,078 documents", which conflated *parseable*
with *populated* and hid 233 editions that are valid JSON containing no
transliteration at all.
"""

import json

import pytest

from oracc_tf import loader, paths

# Fixtures named in P-001 section 4.
STUB = "riao/ria4/Q000000.json"           # valid JSON, zero words
ZERO_BYTE = "rinap/rinap1/Q003424.json"   # 0 bytes as shipped by ORACC
POPULATED = "riao/ria1/Q001801.json"      # ordinary edition


def src(rel):
    sub, name = rel.rsplit("/", 1)
    return paths.DATA / sub / "corpusjson" / name


# --------------------------------------------------------------------------
# scope
# --------------------------------------------------------------------------

def test_edition_scope_is_the_eleven_riao_rinap_subprojects():
    """P-001 section 1: rinap/sources and rinap/scores are out of scope."""
    subs = loader.edition_subprojects(paths.DATA)
    assert subs == [
        "riao/ria1", "riao/ria2", "riao/ria3", "riao/ria4", "riao/ria5",
        "rinap/rinap1", "rinap/rinap2", "rinap/rinap3", "rinap/rinap4",
        "rinap/rinap5", "rinap/rinap5p1",
    ]


# --------------------------------------------------------------------------
# single-file behaviour
# --------------------------------------------------------------------------

def test_zero_byte_file_raises_typed_error():
    with pytest.raises(loader.EmptySourceError) as exc:
        loader.load_edition(src(ZERO_BYTE))
    assert "Q003424" in str(exc.value)


def test_zero_byte_error_is_distinguishable_from_bad_json(tmp_path):
    bad = tmp_path / "Q999999.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(loader.UnparseableSourceError):
        loader.load_edition(bad)
    assert not isinstance(loader.UnparseableSourceError("x"), loader.EmptySourceError)


def test_stub_edition_parses_but_is_not_populated():
    ed = loader.load_edition(src(STUB))
    assert ed.word_count == 0
    assert ed.populated is False
    assert ed.doc["textid"] if "textid" in ed.doc else True   # it is real JSON


def test_populated_edition_reports_words():
    ed = loader.load_edition(src(POPULATED))
    assert ed.populated is True
    assert ed.word_count > 0


def test_document_key_is_subproject_qualified():
    """P-001 section 2.8: bare Q-numbers collide 140 times."""
    ed = loader.load_edition(src(POPULATED))
    assert ed.text_id == "Q001801"
    assert ed.subproject == "riao/ria1"
    assert ed.key == "riao/ria1:Q001801"


# --------------------------------------------------------------------------
# corpus cardinalities - the M0 exit criterion
# --------------------------------------------------------------------------

@pytest.fixture(scope="session")
def survey():
    return loader.survey(paths.DATA)


@pytest.mark.corpus
def test_four_cardinalities_are_reported_separately(survey):
    assert survey.source_files == 2081
    assert survey.parseable == 2078
    assert survey.populated == 1845
    assert survey.stubs == 233


@pytest.mark.corpus
def test_cardinalities_reconcile(survey):
    assert survey.parseable + survey.unreadable == survey.source_files
    assert survey.populated + survey.stubs == survey.parseable


@pytest.mark.corpus
def test_the_three_zero_byte_files_are_named(survey):
    assert sorted(p.name for p in survey.unreadable_paths) == [
        "Q003424.json", "Q006331.json", "Q006333.json",
    ]


@pytest.mark.corpus
def test_composite_keys_are_unique_but_bare_q_numbers_collide(survey):
    """P-001 section 2.8: 140 Q-numbers appear in both rinap5 and rinap5p1."""
    assert len(survey.keys) == survey.parseable
    assert len(set(survey.keys)) == survey.parseable
    bare = [k.split(":", 1)[1] for k in survey.keys]
    assert len(set(bare)) == survey.parseable - 140
