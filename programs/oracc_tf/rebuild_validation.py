"""Source-independent rebuild selection and validation for P-002 Phase 6.

This module deliberately stops short of performing a rebuild.  It models the
stable PH6 boundary that can be tested without live upstream access: selecting
all datasets affected by changed contributors, binding accepted/candidate build
facts to immutable source identities, reconciling the word/document facts PH4
already owns, retaining every validation failure, and rendering deterministic
machine-readable evidence.

Semantic source-sign delta ownership and translation-source delta equations are
not inferred here.  Those remain explicit cross-phase inputs governed by the
reviewed PH4/M9 contract work.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import re
from typing import Any

from . import releases


_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_DATASET_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_CONTRIBUTOR_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]*$")
_CHECK_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
_CHECK_STATUSES = {"pass", "fail", "error"}


class RebuildValidationError(ValueError):
    """PH6 evidence is missing, contradictory, or cannot be compared safely."""


def _nonnegative_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RebuildValidationError(f"{field} must be a non-negative integer")
    return value


def _digest(value: object, field: str) -> str:
    if not isinstance(value, str) or _DIGEST_RE.fullmatch(value) is None:
        raise RebuildValidationError(f"{field} must be a canonical sha256 digest")
    return value


def _dataset(value: object) -> str:
    if not isinstance(value, str) or _DATASET_RE.fullmatch(value) is None:
        raise RebuildValidationError(f"invalid dataset identity: {value!r}")
    return value


def _contributors(values: object, field: str) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise RebuildValidationError(f"{field} must be a tuple")
    if any(
        not isinstance(value, str) or _CONTRIBUTOR_RE.fullmatch(value) is None
        for value in values
    ):
        raise RebuildValidationError(f"{field} contains an invalid contributor identity")
    if len(set(values)) != len(values):
        raise RebuildValidationError(f"{field} contains duplicate contributor identities")
    return values


@dataclass(frozen=True)
class ContributorChanges:
    archives: tuple[str, ...]
    tei: tuple[str, ...]

    def __post_init__(self) -> None:
        _contributors(self.archives, "archives")
        _contributors(self.tei, "tei")


@dataclass(frozen=True)
class BuildCounts:
    documents: int
    populated_documents: int
    words: int
    semantic_signs: int
    synthetic_slots: int
    tf_slots: int
    lines: int
    lexemes: int
    sign_word_membership_errors: int
    word_line_membership_errors: int
    section_path_errors: int

    def __post_init__(self) -> None:
        for field in self.__dataclass_fields__:
            _nonnegative_int(getattr(self, field), field)
        if self.populated_documents > self.documents:
            raise RebuildValidationError("populated_documents cannot exceed documents")
        if self.tf_slots != self.semantic_signs + self.synthetic_slots:
            raise RebuildValidationError(
                "tf_slots must equal semantic_signs + synthetic_slots"
            )


@dataclass(frozen=True)
class RoundTripEvidence:
    source_words: int
    unexplained_words: int

    def __post_init__(self) -> None:
        _nonnegative_int(self.source_words, "roundtrip.source_words")
        _nonnegative_int(self.unexplained_words, "roundtrip.unexplained_words")
        if self.unexplained_words > self.source_words:
            raise RebuildValidationError(
                "roundtrip unexplained_words cannot exceed source_words"
            )


@dataclass(frozen=True)
class TranslationEvidence:
    required: bool
    joined: int | None
    eligible: int | None
    evidence_sha256: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.required, bool):
            raise RebuildValidationError("translation.required must be boolean")
        supplied = (
            self.joined is not None,
            self.eligible is not None,
            self.evidence_sha256 is not None,
        )
        if any(supplied) and not all(supplied):
            raise RebuildValidationError(
                "translation evidence must supply joined, eligible, and digest together"
            )
        if all(supplied):
            joined = _nonnegative_int(self.joined, "translation.joined")
            eligible = _nonnegative_int(self.eligible, "translation.eligible")
            if joined > eligible:
                raise RebuildValidationError("translation.joined cannot exceed eligible")
            _digest(self.evidence_sha256, "translation.evidence_sha256")

    @property
    def present(self) -> bool:
        return (
            self.joined is not None
            and self.eligible is not None
            and self.evidence_sha256 is not None
        )


@dataclass(frozen=True)
class ValidationCheck:
    check_id: str
    status: str
    details: Mapping[str, object]

    def __post_init__(self) -> None:
        if not isinstance(self.check_id, str) or _CHECK_RE.fullmatch(self.check_id) is None:
            raise RebuildValidationError(f"invalid validation check id: {self.check_id!r}")
        if self.status not in _CHECK_STATUSES:
            raise RebuildValidationError(
                f"validation check {self.check_id!r} has invalid status {self.status!r}"
            )
        if not isinstance(self.details, Mapping):
            raise RebuildValidationError("validation check details must be a mapping")


@dataclass(frozen=True)
class BuildValidationRecord:
    dataset: str
    source_state: str
    contributor_manifest_sha256: str
    tf_version: str
    builder_commit: str
    counts: BuildCounts
    roundtrip: RoundTripEvidence
    translation: TranslationEvidence
    checks: tuple[ValidationCheck, ...]

    def __post_init__(self) -> None:
        _dataset(self.dataset)
        _digest(self.source_state, "source_state")
        _digest(self.contributor_manifest_sha256, "contributor_manifest_sha256")
        if not isinstance(self.tf_version, str) or _SEMVER_RE.fullmatch(self.tf_version) is None:
            raise RebuildValidationError(f"invalid TF version: {self.tf_version!r}")
        if not isinstance(self.builder_commit, str) or _COMMIT_RE.fullmatch(self.builder_commit) is None:
            raise RebuildValidationError("builder_commit must be lowercase 40-hex")
        if not isinstance(self.counts, BuildCounts):
            raise RebuildValidationError("counts must be BuildCounts")
        if not isinstance(self.roundtrip, RoundTripEvidence):
            raise RebuildValidationError("roundtrip must be RoundTripEvidence")
        if not isinstance(self.translation, TranslationEvidence):
            raise RebuildValidationError("translation must be TranslationEvidence")
        if not isinstance(self.checks, tuple) or any(
            not isinstance(item, ValidationCheck) for item in self.checks
        ):
            raise RebuildValidationError("checks must be a tuple of ValidationCheck")
        ids = [item.check_id for item in self.checks]
        if len(set(ids)) != len(ids):
            raise RebuildValidationError("build validation checks contain duplicate ids")


@dataclass(frozen=True)
class SourceDeltaEvidence:
    dataset: str
    accepted_source_state: str
    candidate_source_state: str
    accepted_source_words: int
    candidate_source_words: int
    text_word_delta_sum: int
    accepted_documents: int
    candidate_documents: int
    document_delta: int

    def __post_init__(self) -> None:
        _dataset(self.dataset)
        _digest(self.accepted_source_state, "accepted_source_state")
        _digest(self.candidate_source_state, "candidate_source_state")
        before_words = _nonnegative_int(self.accepted_source_words, "accepted_source_words")
        after_words = _nonnegative_int(self.candidate_source_words, "candidate_source_words")
        before_docs = _nonnegative_int(self.accepted_documents, "accepted_documents")
        after_docs = _nonnegative_int(self.candidate_documents, "candidate_documents")
        if isinstance(self.text_word_delta_sum, bool) or not isinstance(self.text_word_delta_sum, int):
            raise RebuildValidationError("text_word_delta_sum must be an integer")
        if isinstance(self.document_delta, bool) or not isinstance(self.document_delta, int):
            raise RebuildValidationError("document_delta must be an integer")
        if after_words - before_words != self.text_word_delta_sum:
            raise RebuildValidationError(
                "source word totals disagree with text_word_delta_sum"
            )
        if after_docs - before_docs != self.document_delta:
            raise RebuildValidationError(
                "source document totals disagree with document_delta"
            )


@dataclass(frozen=True)
class ValidationReport:
    dataset: str
    accepted_source_state: str
    candidate_source_state: str
    accepted_build_record_sha256: str
    candidate_build_record_sha256: str
    status: str
    checks: tuple[ValidationCheck, ...]
    passed_check_ids: tuple[str, ...]
    blocking_check_ids: tuple[str, ...]


def affected_datasets(
    dataset_inputs: Mapping[str, releases.DatasetInputs],
    changes: ContributorChanges,
) -> tuple[str, ...]:
    """Return all active datasets owning any changed JSON or TEI contributor."""
    if not isinstance(dataset_inputs, Mapping) or not dataset_inputs:
        raise RebuildValidationError("dataset_inputs must be a non-empty mapping")
    if not isinstance(changes, ContributorChanges):
        raise RebuildValidationError("changes must be ContributorChanges")

    owners: dict[tuple[str, str], list[str]] = {}
    for dataset_name in sorted(dataset_inputs):
        _dataset(dataset_name)
        inputs = dataset_inputs[dataset_name]
        if not isinstance(inputs, releases.DatasetInputs):
            raise RebuildValidationError(
                f"dataset {dataset_name!r} has invalid DatasetInputs"
            )
        archives = tuple(inputs.archives)
        tei = tuple(inputs.tei)
        if len(set(archives)) != len(archives) or len(set(tei)) != len(tei):
            raise RebuildValidationError(
                f"dataset {dataset_name!r} contains duplicate contributor inputs"
            )
        for item in archives:
            owners.setdefault(("archive", item), []).append(dataset_name)
        for item in tei:
            owners.setdefault(("tei", item), []).append(dataset_name)

    selected: set[str] = set()
    missing: list[str] = []
    for kind, values in (("archive", changes.archives), ("tei", changes.tei)):
        for value in values:
            matches = owners.get((kind, value), [])
            if not matches:
                missing.append(f"{kind}:{value}")
            selected.update(matches)
    if missing:
        raise RebuildValidationError(
            "changed contributors are not mapped to an active dataset: "
            + ", ".join(sorted(missing))
        )
    return tuple(sorted(selected))


def _json_value(value: object) -> object:
    if hasattr(value, "__dataclass_fields__"):
        return {key: _json_value(item) for key, item in asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise RebuildValidationError(
        f"validation evidence contains non-JSON value {type(value).__name__}"
    )


def _canonical_bytes(value: object) -> bytes:
    try:
        return (
            json.dumps(
                _json_value(value),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise RebuildValidationError("validation evidence is not canonical JSON") from exc


def build_record_sha256(record: BuildValidationRecord) -> str:
    if not isinstance(record, BuildValidationRecord):
        raise RebuildValidationError("record must be BuildValidationRecord")
    return "sha256:" + sha256(_canonical_bytes(record)).hexdigest()


def _check(check_id: str, status: str, **details: object) -> ValidationCheck:
    return ValidationCheck(check_id, status, details)


def validate_candidate(
    accepted: BuildValidationRecord | None,
    candidate: BuildValidationRecord,
    source_delta: SourceDeltaEvidence,
) -> ValidationReport:
    """Compare one candidate build with the immutable last accepted build record."""
    if accepted is None:
        raise RebuildValidationError(
            "update validation requires the last accepted build-validation record"
        )
    if not isinstance(accepted, BuildValidationRecord):
        raise RebuildValidationError("accepted must be BuildValidationRecord")
    if not isinstance(candidate, BuildValidationRecord):
        raise RebuildValidationError("candidate must be BuildValidationRecord")
    if not isinstance(source_delta, SourceDeltaEvidence):
        raise RebuildValidationError("source_delta must be SourceDeltaEvidence")

    if accepted.dataset != candidate.dataset or accepted.dataset != source_delta.dataset:
        raise RebuildValidationError("dataset identity differs across validation evidence")
    if accepted.source_state != source_delta.accepted_source_state:
        raise RebuildValidationError("accepted build/source identity mismatch")
    if candidate.source_state != source_delta.candidate_source_state:
        raise RebuildValidationError("candidate build/source identity mismatch")

    checks: list[ValidationCheck] = list(candidate.checks)
    explicit_ids = {check.check_id for check in checks}

    word_ok = (
        accepted.counts.words == source_delta.accepted_source_words
        and candidate.counts.words == source_delta.candidate_source_words
        and candidate.counts.words - accepted.counts.words
        == source_delta.text_word_delta_sum
    )
    if "source-word-reconciliation" not in explicit_ids:
        checks.append(
            _check(
                "source-word-reconciliation",
                "pass" if word_ok else "fail",
                accepted_build_words=accepted.counts.words,
                candidate_build_words=candidate.counts.words,
                accepted_source_words=source_delta.accepted_source_words,
                candidate_source_words=source_delta.candidate_source_words,
                source_text_word_delta=source_delta.text_word_delta_sum,
            )
        )

    document_ok = (
        accepted.counts.documents == source_delta.accepted_documents
        and candidate.counts.documents == source_delta.candidate_documents
        and candidate.counts.documents - accepted.counts.documents
        == source_delta.document_delta
    )
    if "source-document-reconciliation" not in explicit_ids:
        checks.append(
            _check(
                "source-document-reconciliation",
                "pass" if document_ok else "fail",
                accepted_build_documents=accepted.counts.documents,
                candidate_build_documents=candidate.counts.documents,
                accepted_source_documents=source_delta.accepted_documents,
                candidate_source_documents=source_delta.candidate_documents,
                source_document_delta=source_delta.document_delta,
            )
        )

    if (
        accepted.source_state == candidate.source_state
        and accepted.tf_version == candidate.tf_version
        and accepted.counts != candidate.counts
        and "unchanged-source-count-drift" not in explicit_ids
    ):
        checks.append(
            _check(
                "unchanged-source-count-drift",
                "fail",
                accepted_counts=_json_value(accepted.counts),
                candidate_counts=_json_value(candidate.counts),
            )
        )
    elif "unchanged-source-count-drift" not in explicit_ids:
        checks.append(_check("unchanged-source-count-drift", "pass"))

    membership_errors = (
        candidate.counts.sign_word_membership_errors
        + candidate.counts.word_line_membership_errors
        + candidate.counts.section_path_errors
    )
    if "m6-membership" not in explicit_ids:
        checks.append(
            _check(
                "m6-membership",
                "pass" if membership_errors == 0 else "fail",
                sign_word_membership_errors=candidate.counts.sign_word_membership_errors,
                word_line_membership_errors=candidate.counts.word_line_membership_errors,
                section_path_errors=candidate.counts.section_path_errors,
            )
        )

    roundtrip_ok = (
        candidate.roundtrip.source_words == candidate.counts.words
        and candidate.roundtrip.unexplained_words == 0
    )
    if "roundtrip-evidence" not in explicit_ids:
        checks.append(
            _check(
                "roundtrip-evidence",
                "pass" if roundtrip_ok else "fail",
                source_words=candidate.roundtrip.source_words,
                build_words=candidate.counts.words,
                unexplained_words=candidate.roundtrip.unexplained_words,
            )
        )

    if candidate.translation.required and not candidate.translation.present:
        if "translation-evidence-missing" not in explicit_ids:
            checks.append(
                _check(
                    "translation-evidence-missing",
                    "error",
                    required=True,
                )
            )
    elif candidate.translation.present and "translation-evidence-present" not in explicit_ids:
        checks.append(
            _check(
                "translation-evidence-present",
                "pass",
                required=candidate.translation.required,
                evidence_sha256=candidate.translation.evidence_sha256,
            )
        )

    seen: set[str] = set()
    for check in checks:
        if check.check_id in seen:
            raise RebuildValidationError(
                f"duplicate validation check id after reconciliation: {check.check_id}"
            )
        seen.add(check.check_id)

    passed = tuple(check.check_id for check in checks if check.status == "pass")
    blocking = tuple(check.check_id for check in checks if check.status in {"fail", "error"})
    if any(check.status == "error" for check in checks):
        status = "error"
    elif any(check.status == "fail" for check in checks):
        status = "blocked"
    else:
        status = "pass"

    return ValidationReport(
        dataset=candidate.dataset,
        accepted_source_state=accepted.source_state,
        candidate_source_state=candidate.source_state,
        accepted_build_record_sha256=build_record_sha256(accepted),
        candidate_build_record_sha256=build_record_sha256(candidate),
        status=status,
        checks=tuple(checks),
        passed_check_ids=passed,
        blocking_check_ids=blocking,
    )


def render_validation_report(report: ValidationReport) -> bytes:
    """Serialize PH6 validation evidence deterministically with one trailing newline."""
    if not isinstance(report, ValidationReport):
        raise RebuildValidationError("report must be ValidationReport")
    return (
        json.dumps(
            _json_value(report),
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


__all__ = [
    "BuildCounts",
    "BuildValidationRecord",
    "ContributorChanges",
    "RebuildValidationError",
    "RoundTripEvidence",
    "SourceDeltaEvidence",
    "TranslationEvidence",
    "ValidationCheck",
    "ValidationReport",
    "affected_datasets",
    "build_record_sha256",
    "render_validation_report",
    "validate_candidate",
]
