"""Filesystem layout.

Nothing outside this module should hard-code a path into the corpus.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
DOCS = ROOT / "docs"
REPORTS = ROOT / "reports"

CORPUSJSON = "corpusjson"

#: Subprojects that are score/source witness editions rather than annotated
#: editions. P-001 section 1: they are 0% lemmatised and out of scope.
WITNESS_SUBPROJECTS = frozenset({"sources", "scores"})

#: Projects contributing to the joined RIAO + RINAP dataset.
EDITION_PROJECTS = ("riao", "rinap")
