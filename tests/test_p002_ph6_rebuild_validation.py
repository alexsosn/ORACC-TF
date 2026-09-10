"""P-002 PH6 RED contracts for deterministic rebuild selection/validation."""

from __future__ import annotations

import importlib
import json

import pytest

from oracc_tf import releases


STATE_A = "sha256:" + "a" * 64
STATE_B = "sha256:" + "b" * 64
STATE_C = "sha256:" + "c" * 64
MANIFEST_A = "sha256:" + "d" * 64
MANIFEST_B = "sha256:" + "e" * 64
COMMIT = "f" * 40
TF_VERSION = "0.2.0"


def api():
    return importlib.import_module("oracc_tf.rebuild_validation")


def dataset_inputs():
    return {
        "alpha": releases.DatasetInputs(
            archives=("alpha-a", "shared"),
            tei=("alpha-tei",),
        ),
        "beta": releases.DatasetInputs(
            archives=("beta-a", "shared"),
            tei=(),
        ),
    }


def counts(
    module,
    *,
    documents: int = 2,
    words: int = 10,
    semantic_signs: int = 20,
    synthetic_slots: int = 1,
    tf_slots: int = 21,
    membership_errors: int = 0,
    section_path_errors: int = 0,
):
    return module.BuildCounts(
        documents=documents,
        populated_documents=documents,
        words=words,
        semantic_signs=semantic_signs,
        synthetic_slots=synthetic_slots,
        tf_slots=tf_slots,
        lines=4,
        lexemes=5,
        sign_word_membership_errors=membership_errors,
        word_line_membership_errors=membership_errors,
        section_path_errors=section_path_errors,
    )


def translation(module, *, required: bool = False, present: bool = False):
    return module.TranslationEvidence(
        required=required,
        joined=2 if present else None,
        eligible=2 if present else None,
        evidence_sha256=("sha256:" + "9" * 64) if present else None,
    )


def record(
    module,
    *,
    dataset: str = "alpha",
    state: str = STATE_A,
    manifest: str = MANIFEST_A,
    build_counts=None,
    translation_evidence=None,
    checks=(),
):
    return module.BuildValidationRecord(
        dataset=dataset,
        source_state=state,
        contributor_manifest_sha256=manifest,
        tf_version=TF_VERSION,
        builder_commit=COMMIT,
        counts=build_counts or counts(module),
        roundtrip=module.RoundTripEvidence(source_words=(build_counts or counts(module)).words, unexplained_words=0),
        translation=translation_evidence or translation(module),
        checks=tuple(checks),
    )


def source_delta(
    module,
    *,
    before_state: str = STATE_A,
    after_state: str = STATE_B,
    before_words: int = 10,
    after_words: int = 12,
    text_word_delta_sum: int = 2,
    before_documents: int = 2,
    after_documents: int = 3,
    document_delta: int = 1,
):
    return module.SourceDeltaEvidence(
        dataset="alpha",
        accepted_source_state=before_state,
        candidate_source_state=after_state,
        accepted_source_words=before_words,
        candidate_source_words=after_words,
        text_word_delta_sum=text_word_delta_sum,
        accepted_documents=before_documents,
        candidate_documents=after_documents,
        document_delta=document_delta,
    )


def test_archive_change_selects_only_dataset_that_owns_it() -> None:
    module = api()
    changes = module.ContributorChanges(archives=("alpha-a",), tei=())

    assert module.affected_datasets(dataset_inputs(), changes) == ("alpha",)


def test_shared_archive_change_selects_every_owner_once_deterministically() -> None:
    module = api()
    changes = module.ContributorChanges(archives=("shared",), tei=())

    assert module.affected_datasets(dataset_inputs(), changes) == ("alpha", "beta")


def test_tei_only_change_selects_owning_dataset_without_json_change() -> None:
    module = api()
    changes = module.ContributorChanges(archives=(), tei=("alpha-tei",))

    assert module.affected_datasets(dataset_inputs(), changes) == ("alpha",)


def test_unmapped_changed_contributor_fails_closed() -> None:
    module = api()
    changes = module.ContributorChanges(archives=("not-registered",), tei=())

    with pytest.raises(module.RebuildValidationError):
        module.affected_datasets(dataset_inputs(), changes)


def test_duplicate_changed_contributor_is_rejected() -> None:
    module = api()

    with pytest.raises(module.RebuildValidationError):
        module.ContributorChanges(archives=("shared", "shared"), tei=())


def test_update_validation_requires_last_accepted_build_record() -> None:
    module = api()
    candidate = record(
        module,
        state=STATE_B,
        manifest=MANIFEST_B,
        build_counts=counts(module, documents=3, words=12),
    )

    with pytest.raises(module.RebuildValidationError):
        module.validate_candidate(None, candidate, source_delta(module))


def test_source_and_build_identity_mismatch_fails_before_delta_math() -> None:
    module = api()
    accepted = record(module, state=STATE_A)
    candidate = record(
        module,
        state=STATE_C,
        manifest=MANIFEST_B,
        build_counts=counts(module, documents=3, words=12),
    )

    with pytest.raises(module.RebuildValidationError):
        module.validate_candidate(accepted, candidate, source_delta(module, after_state=STATE_B))


def test_explained_word_and_document_deltas_pass_source_reconciliation() -> None:
    module = api()
    accepted = record(module, state=STATE_A, build_counts=counts(module, documents=2, words=10))
    candidate = record(
        module,
        state=STATE_B,
        manifest=MANIFEST_B,
        build_counts=counts(module, documents=3, words=12),
    )

    report = module.validate_candidate(accepted, candidate, source_delta(module))

    assert report.status == "pass"
    assert "source-word-reconciliation" in report.passed_check_ids
    assert "source-document-reconciliation" in report.passed_check_ids
    assert report.blocking_check_ids == ()


def test_unexplained_word_delta_blocks_even_when_other_counts_match() -> None:
    module = api()
    accepted = record(module, state=STATE_A, build_counts=counts(module, documents=2, words=10))
    candidate = record(
        module,
        state=STATE_B,
        manifest=MANIFEST_B,
        build_counts=counts(module, documents=3, words=13),
    )

    report = module.validate_candidate(accepted, candidate, source_delta(module))

    assert report.status == "blocked"
    assert "source-word-reconciliation" in report.blocking_check_ids


def test_unchanged_source_and_schema_reject_semantic_count_drift() -> None:
    module = api()
    accepted = record(module, state=STATE_A, build_counts=counts(module, semantic_signs=20))
    candidate = record(module, state=STATE_A, build_counts=counts(module, semantic_signs=21))
    delta = source_delta(
        module,
        before_state=STATE_A,
        after_state=STATE_A,
        before_words=10,
        after_words=10,
        text_word_delta_sum=0,
        before_documents=2,
        after_documents=2,
        document_delta=0,
    )

    report = module.validate_candidate(accepted, candidate, delta)

    assert report.status == "blocked"
    assert "unchanged-source-count-drift" in report.blocking_check_ids


def test_multiple_failed_invariants_are_all_preserved_not_short_circuited() -> None:
    module = api()
    accepted = record(module, state=STATE_A)
    candidate = record(
        module,
        state=STATE_B,
        manifest=MANIFEST_B,
        build_counts=counts(module, documents=3, words=12),
        checks=(
            module.ValidationCheck("m1-disposition", "fail", {"unknown": 1}),
            module.ValidationCheck("tf-load", "fail", {"loaded": False}),
            module.ValidationCheck("roundtrip", "pass", {"unexplained": 0}),
        ),
    )

    report = module.validate_candidate(accepted, candidate, source_delta(module))

    assert report.status == "blocked"
    assert report.blocking_check_ids == ("m1-disposition", "tf-load")
    assert "roundtrip" in report.passed_check_ids


def test_translation_required_without_authenticated_evidence_is_error() -> None:
    module = api()
    accepted = record(module, state=STATE_A, translation_evidence=translation(module, required=True, present=True))
    candidate = record(
        module,
        state=STATE_B,
        manifest=MANIFEST_B,
        build_counts=counts(module, documents=3, words=12),
        translation_evidence=translation(module, required=True, present=False),
    )

    report = module.validate_candidate(accepted, candidate, source_delta(module))

    assert report.status == "error"
    assert "translation-evidence-missing" in report.blocking_check_ids


def test_explicit_translation_free_scope_does_not_fabricate_coverage() -> None:
    module = api()
    accepted = record(module, state=STATE_A, translation_evidence=translation(module, required=False, present=False))
    candidate = record(
        module,
        state=STATE_B,
        manifest=MANIFEST_B,
        build_counts=counts(module, documents=3, words=12),
        translation_evidence=translation(module, required=False, present=False),
    )

    report = module.validate_candidate(accepted, candidate, source_delta(module))

    assert "translation-evidence-missing" not in report.blocking_check_ids


def test_validation_report_serialization_is_deterministic_and_identity_bound() -> None:
    module = api()
    accepted = record(module, state=STATE_A, build_counts=counts(module, documents=2, words=10))
    candidate = record(
        module,
        state=STATE_B,
        manifest=MANIFEST_B,
        build_counts=counts(module, documents=3, words=12),
    )
    report = module.validate_candidate(accepted, candidate, source_delta(module))

    first = module.render_validation_report(report)
    second = module.render_validation_report(report)

    assert first == second
    assert first.endswith(b"\n")
    decoded = json.loads(first)
    assert decoded["dataset"] == "alpha"
    assert decoded["accepted_source_state"] == STATE_A
    assert decoded["candidate_source_state"] == STATE_B
    assert decoded["accepted_build_record_sha256"].startswith("sha256:")
    assert decoded["candidate_build_record_sha256"].startswith("sha256:")
