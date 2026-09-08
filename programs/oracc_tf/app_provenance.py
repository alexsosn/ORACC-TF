"""Release-derived app provenance and collision-safe ORACC document links.

This module is deliberately independent of Text-Fabric app packaging.  It turns
an already validated distribution manifest into the small release record later
app/browser layers may expose, and it derives document links only from
source-provided ORACC project identity.  It does not invent DOI/licence facts,
passage anchors, or lexeme identifiers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
from typing import Mapping
from urllib.parse import urlsplit


_MANIFEST_SCHEMA_VERSION = 3
_DATASET_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_TEXT_ID_RE = re.compile(r"^Q[0-9]{6}$")
_PROJECT_COMPONENT_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_RELEASE_RECORD_FIELDS = (
    "tf_version",
    "tf_root",
    "builder_commit",
    "source_state",
    "provenance_complete",
    "tree_digest",
)


class AppProvenanceError(ValueError):
    """Manifest/source state cannot safely drive app provenance or links."""


@dataclass(frozen=True)
class ReleaseProvenance:
    dataset: str
    repository: str
    release_id: str
    tf_version: str
    builder_commit: str
    source_state: str | None
    tree_digest: str


def _require_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise AppProvenanceError(f"{field} must be a non-empty trimmed string")
    if any(ord(char) < 0x20 for char in value):
        raise AppProvenanceError(f"{field} contains control characters")
    return value


def _validate_project(value: object, field: str) -> str:
    project = _require_string(value, field)
    parts = project.split("/")
    if len(parts) < 2 or any(not _PROJECT_COMPONENT_RE.fullmatch(part) for part in parts):
        raise AppProvenanceError(f"{field} is not a safe ORACC project path: {project!r}")
    return project


def _validate_release_record(
    record: object,
    *,
    dataset: str,
    release_id: str,
) -> dict[str, object]:
    if not isinstance(record, Mapping) or set(record) != set(_RELEASE_RECORD_FIELDS):
        raise AppProvenanceError(f"release {release_id!r} has invalid fields")

    tf_version = _require_string(record.get("tf_version"), "tf_version")
    tf_root = _require_string(record.get("tf_root"), "tf_root")
    if tf_root != f"{dataset}/tf/{tf_version}":
        raise AppProvenanceError("release TF root is not canonical for dataset/version")

    builder_commit = record.get("builder_commit")
    if not isinstance(builder_commit, str) or not _COMMIT_RE.fullmatch(builder_commit):
        raise AppProvenanceError("builder_commit must be a lowercase 40-hex commit id")

    source_state = record.get("source_state")
    if source_state is not None and (
        not isinstance(source_state, str) or not _DIGEST_RE.fullmatch(source_state)
    ):
        raise AppProvenanceError("source_state must be null or a canonical sha256 digest")

    provenance_complete = record.get("provenance_complete")
    if not isinstance(provenance_complete, bool) or provenance_complete != (source_state is not None):
        raise AppProvenanceError("provenance_complete is inconsistent with source_state")

    tree_digest = record.get("tree_digest")
    if not isinstance(tree_digest, str) or not _DIGEST_RE.fullmatch(tree_digest):
        raise AppProvenanceError("tree_digest must be a canonical sha256 digest")

    return dict(record)


def release_provenance(manifest: Mapping[str, object]) -> ReleaseProvenance:
    """Return app-facing release facts from the current immutable manifest entry.

    The top-level current-release fields are cross-checked against the immutable
    release ledger and visible-root ownership.  This prevents an app header from
    silently reporting a release state different from the bytes it accompanies.
    """
    if not isinstance(manifest, Mapping):
        raise AppProvenanceError("distribution manifest must be a mapping")
    if manifest.get("schema_version") != _MANIFEST_SCHEMA_VERSION:
        raise AppProvenanceError(
            f"unsupported distribution manifest schema: {manifest.get('schema_version')!r}"
        )

    dataset = _require_string(manifest.get("dataset"), "dataset")
    if not _DATASET_RE.fullmatch(dataset):
        raise AppProvenanceError(f"invalid dataset identity: {dataset!r}")

    repository = _require_string(manifest.get("repository"), "repository")
    if repository != f"ORACC-TF-{dataset}":
        raise AppProvenanceError("repository does not match semantic dataset identity")

    release_id = _require_string(manifest.get("release_id"), "release_id")
    releases = manifest.get("releases")
    if not isinstance(releases, Mapping) or release_id not in releases:
        raise AppProvenanceError("current release_id is absent from immutable release ledger")

    ledger_record = _validate_release_record(
        releases[release_id], dataset=dataset, release_id=release_id
    )
    top_record = {field: manifest.get(field) for field in _RELEASE_RECORD_FIELDS}
    if top_record != ledger_record:
        raise AppProvenanceError("current release fields drift from immutable release ledger")

    tf_root = ledger_record["tf_root"]
    visible_roots = manifest.get("visible_roots")
    if (
        not isinstance(visible_roots, Mapping)
        or visible_roots.get(tf_root) != release_id
    ):
        raise AppProvenanceError("current TF root is not owned by the current release")

    return ReleaseProvenance(
        dataset=dataset,
        repository=repository,
        release_id=release_id,
        tf_version=ledger_record["tf_version"],  # type: ignore[arg-type]
        builder_commit=ledger_record["builder_commit"],  # type: ignore[arg-type]
        source_state=ledger_record["source_state"],  # type: ignore[arg-type]
        tree_digest=ledger_record["tree_digest"],  # type: ignore[arg-type]
    )


def render_release_provenance(record: ReleaseProvenance) -> bytes:
    """Serialize app-facing provenance deterministically for generated artifacts."""
    if not isinstance(record, ReleaseProvenance):
        raise AppProvenanceError("release provenance must be a ReleaseProvenance record")
    return (
        json.dumps(asdict(record), sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def official_document_url(
    *,
    subproject: str,
    text_id: str,
    source_url: object,
    source_project: object,
) -> str | None:
    """Return a verified official ORACC document URL, or omit it when absent.

    A bare Q-number is never sufficient: the source-provided project identity
    and project URL must agree with the qualified ORACC-TF subproject.  Present
    but unsafe/inconsistent metadata fails closed instead of producing a guess.
    """
    project = _validate_project(subproject, "subproject")
    if not isinstance(text_id, str) or not _TEXT_ID_RE.fullmatch(text_id):
        raise AppProvenanceError(f"invalid ORACC text id: {text_id!r}")

    if source_url is None:
        return None
    if not isinstance(source_url, str) or not source_url or source_url != source_url.strip():
        raise AppProvenanceError("source URL must be a non-empty trimmed string when present")

    reported_project = _validate_project(source_project, "source_project")
    if reported_project != project:
        raise AppProvenanceError("source project does not match qualified document subproject")

    parsed = urlsplit(source_url)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise AppProvenanceError("source URL must use HTTP(S)")
    if parsed.username is not None or parsed.password is not None:
        raise AppProvenanceError("source URL must not contain user information")
    try:
        port = parsed.port
    except ValueError as exc:
        raise AppProvenanceError("source URL contains an invalid port") from exc
    if port is not None:
        raise AppProvenanceError("source URL must not contain an explicit port")
    if parsed.hostname is None or parsed.hostname.lower() != "oracc.org":
        raise AppProvenanceError("source URL host is not the official ORACC host")
    if parsed.query or parsed.fragment:
        raise AppProvenanceError("source URL must not contain query or fragment data")
    if "%" in parsed.path or "\\" in parsed.path:
        raise AppProvenanceError("source URL path must be literal and unambiguous")

    expected_path = f"/{project}"
    if parsed.path.rstrip("/") != expected_path:
        raise AppProvenanceError("source URL path does not match qualified document subproject")

    return f"{parsed.scheme.lower()}://oracc.org/{project}/{text_id}/"


__all__ = [
    "AppProvenanceError",
    "ReleaseProvenance",
    "official_document_url",
    "release_provenance",
    "render_release_provenance",
]
