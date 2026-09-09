"""RED contract for synchronizing reviewed PH5 research into R-002/P-002."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
R002 = ROOT / "docs" / "research" / "R-002-upstream-automation.md"
P002 = ROOT / "docs" / "plans" / "P-002-upstream-automation.md"
CONTRACT = "issue-95-ph5-gate-contracts.json"
STALE_APPROVAL_TUPLE = "(archive sha256, text id, condition)"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _assert_common_normative_contract(text: str) -> None:
    """Require durable PH5 safety anchors without pinning whole prose."""
    for required in (
        CONTRACT,
        "GateFinding",
        "subject.scope",
        "condition_sha256",
        "evidence_fingerprint",
        "evaluation-error",
        "last accepted",
        "dataset-input-set-changed",
        "prebuild",
        "postbuild",
        "TOCTOU",
    ):
        assert required in text, required
    assert STALE_APPROVAL_TUPLE not in text


def test_r002_normatively_adopts_reviewed_ph5_contract():
    text = _text(R002)
    _assert_common_normative_contract(text)
    for required in (
        "accepted dataset",
        "candidate dataset",
        "project-inventory",
        "ArchiveLock.extract_paths",
        "TEI",
        "never disables gate execution",
        "blocked candidate",
    ):
        assert required in text, required


def test_p002_orchestrates_two_stage_ph5_without_baseline_laundering():
    text = _text(P002)
    _assert_common_normative_contract(text)
    for required in (
        "PH5 prebuild",
        "PH5 postbuild",
        "candidate_build_source_words",
        "candidate_PH4_source_words",
        "accepted_build_source_words",
        "ph4_text_word_delta_sum",
        "blocked candidate",
        "accepted and candidate",
    ):
        assert required in text, required


def test_p002_definition_of_done_rejects_stale_approval_and_missing_evidence():
    text = _text(P002)
    dod = text.split("# Definition of done", 1)[1]
    for required in (
        "typed subject",
        "evidence fingerprint",
        "evaluation-error",
        "contributor",
        "TOCTOU",
    ):
        assert required in dod, required


def test_lemma_coverage_scope_is_exact_subproject_not_project():
    r002 = _text(R002)
    p002 = _text(P002)
    assert "lemma coverage drops > 2 points for a subproject" in r002
    assert "- lemma-coverage delta per subproject" in p002
    assert "lemma coverage drops > 2 points for a project" not in r002
    assert "- lemma-coverage delta per project" not in p002
