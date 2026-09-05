"""Filesystem layout.

Nothing outside this module should hard-code a path into the corpus.
"""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
DOCS = ROOT / "docs"
REPORTS = ROOT / "reports"

CORPUSJSON = "corpusjson"

_DATASET_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


#: Subprojects that are score/source witness editions rather than annotated
#: editions. P-001 section 1: they are 0% lemmatised and out of scope.
WITNESS_SUBPROJECTS = frozenset({"sources", "scores"})

#: Projects contributing to the joined RIAO + RINAP dataset.
EDITION_PROJECTS = ("riao", "rinap")


def publishable_tf_root(
    output_base: Path | str,
    dataset: str,
    tf_version: str,
) -> Path:
    """Return the canonical standalone Text-Fabric root for one dataset version.

    The stable filesystem identity intentionally excludes upstream timestamps
    and source-state digests. Those belong to release/provenance metadata.
    """
    if not isinstance(dataset, str) or not _DATASET_NAME_RE.fullmatch(dataset):
        raise ValueError(f"invalid dataset identifier: {dataset!r}")

    # Reuse the release model's SemVer parser instead of maintaining a second
    # version grammar in filesystem code. Import locally to keep paths.py a
    # lightweight dependency for source-reading modules.
    from .releases import ReleaseModelError, semver_precedence_key

    try:
        semver_precedence_key(tf_version)
    except (ReleaseModelError, TypeError) as exc:
        raise ValueError(f"invalid TF version: {tf_version!r}") from exc

    return Path(output_base) / dataset / "tf" / tf_version
