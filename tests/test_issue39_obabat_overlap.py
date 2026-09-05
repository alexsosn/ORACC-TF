"""Research-gate tests for issue #39 OBABAT/Nino overlap comparison."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "compare_obabat_overlap.py"
spec = spec_from_file_location("compare_obabat_overlap", SCRIPT)
module = module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def test_normalize_p_id_strips_whitespace_but_not_identity():
    assert module.normalize_p_id("  P510527\n") == "P510527"

    with pytest.raises(module.ComparisonError, match="invalid CDLI P-number"):
        module.normalize_p_id("p510527")


def test_duplicate_ids_fail_closed_after_normalization():
    with pytest.raises(module.ComparisonError, match="duplicate"):
        module.unique_p_ids(["P510527", " P510527 "], source="fixture")


def test_missing_or_invalid_ids_fail_closed():
    with pytest.raises(module.ComparisonError, match="missing CDLI P-number"):
        module.normalize_p_id(None)

    with pytest.raises(module.ComparisonError, match="invalid CDLI P-number"):
        module.unique_p_ids(["P510527", ""], source="fixture")


def test_exact_set_comparison_keeps_reference_only_separate():
    result = module.compare_id_sets(
        ["P510527", "P510530", "P511156"],
        ["P510527", "P510530", "P509373"],
    )

    assert result["overlap_ids"] == ["P510527", "P510530"]
    assert result["not_in_reference_ids"] == ["P511156"]
    assert result["reference_only_ids"] == ["P509373"]


def test_content_match_with_distinct_ids_is_not_promoted_to_same_document():
    result = module.classify_pair(
        "P510527",
        "P510530",
        left_text="a-na  DINGIR-šu-ib-ni",
        right_text="a-na DINGIR-šu-ib-ni",
    )

    assert result == "content_match_distinct_ids"


def test_ambiguous_distinct_ids_without_strong_content_match_remain_unresolved():
    assert (
        module.classify_pair("P510527", "P510530", left_text=None, right_text=None)
        == "unresolved"
    )
    assert (
        module.classify_pair(
            "P510527", "P510530", left_text="a-na", right_text="a-na-ku"
        )
        == "unresolved"
    )


def test_exact_identifier_wins_without_requiring_content():
    assert module.classify_pair("P510527", " P510527 ") == "exact_identifier"


def test_committed_manifest_partitions_the_exact_pinned_oracc_source():
    result = module.validate_manifest_against_oracc(
        ROOT / "data" / "obabat" / "atletters" / "corpus.json",
        ROOT / "docs" / "research" / "issue-39-obabat-overlap.json",
    )

    assert result == {
        "oracc_documents": 121,
        "overlap_documents": 86,
        "not_in_pinned_nino_documents": 35,
    }


def test_manifest_validation_rejects_source_bytes_that_no_longer_match_pin(tmp_path):
    source = ROOT / "data" / "obabat" / "atletters" / "corpus.json"
    changed = tmp_path / "corpus.json"
    changed.write_bytes(source.read_bytes() + b"\n")

    with pytest.raises(module.ComparisonError, match="blob SHA"):
        module.validate_manifest_against_oracc(
            changed,
            ROOT / "docs" / "research" / "issue-39-obabat-overlap.json",
        )
