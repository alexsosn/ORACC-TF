"""Read ORACC corpusjson editions and report what is actually there.

P-001 section 2.1 records four different counts that revision 1 of the plan
collapsed into one. They must stay separate, because they differ:

    source files   every corpusjson/*.json in scope          2,081
    parseable      those that are valid JSON                 2,078
    populated      those containing at least one word        1,845
    stubs          valid JSON with no transliteration at all   233

The 233 stubs are not a corner case. They are 11% of parseable files and
carry the full text/discourse/sentence skeleton with an empty body, so any
check that only looks for well-formed JSON will treat them as real editions.

Three files are zero bytes as shipped by ORACC. They raise EmptySourceError
rather than the generic parse error, so a caller can tell "upstream shipped
nothing" apart from "we cannot read this".
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Sequence

from . import paths


class SourceError(Exception):
    """Base class for a corpusjson file we cannot turn into an Edition."""


class EmptySourceError(SourceError):
    """The source file is zero bytes.

    ORACC ships three of these in rinap1. Extraction was verified clean
    against the ZIP manifests, so this is upstream state, not local damage.
    """


class UnparseableSourceError(SourceError):
    """The source file is not valid JSON."""


@dataclass(frozen=True)
class Edition:
    """One ORACC composite edition."""

    subproject: str
    text_id: str
    path: Path
    doc: dict = field(repr=False)
    word_count: int

    @property
    def key(self) -> str:
        """Document identity.

        Subproject-qualified because bare Q-numbers are not unique: 140
        collide between rinap5 and rinap5p1, and 48 of those differ in
        content (P-001 section 2.8). Keying on the Q-number alone silently
        merges two editions.
        """
        return f"{self.subproject}:{self.text_id}"

    @property
    def populated(self) -> bool:
        return self.word_count > 0


@dataclass(frozen=True)
class Survey:
    """The four cardinalities, kept separate."""

    source_files: int
    parseable: int
    populated: int
    stubs: int
    unreadable: int
    unreadable_paths: tuple[Path, ...]
    stub_keys: tuple[str, ...]
    keys: tuple[str, ...]

    def report(self) -> str:
        return (
            f"source files : {self.source_files:>6,}\n"
            f"parseable    : {self.parseable:>6,}   ({self.unreadable} unreadable)\n"
            f"populated    : {self.populated:>6,}\n"
            f"stubs        : {self.stubs:>6,}   valid JSON, no transliteration"
        )


def count_words(doc: dict) -> int:
    """Number of CDL lemma ("l") nodes in a document.

    The CDL tree nests through "cdl" lists; d/c/l nodes are siblings within
    them (P-001 section 2.4).
    """
    total = 0
    stack = [doc]
    while stack:
        node = stack.pop()
        if node.get("node") == "l":
            total += 1
        stack.extend(node.get("cdl") or [])
    return total


def subproject_of(path: Path) -> str:
    """"riao/ria1" for data/riao/ria1/corpusjson/Q001801.json."""
    parts = path.resolve().parts
    try:
        i = len(parts) - 1 - parts[::-1].index(paths.CORPUSJSON)
    except ValueError:
        return path.parent.name
    return "/".join(parts[i - 2:i])


def load_edition(path: Path) -> Edition:
    """Parse one corpusjson file.

    Raises EmptySourceError for a zero-byte file and UnparseableSourceError
    for invalid JSON. Both carry the file name, since callers report them.
    """
    path = Path(path)
    if path.stat().st_size == 0:
        raise EmptySourceError(f"{path.name}: zero-byte source file ({path})")
    try:
        with open(path, encoding="utf-8") as handle:
            doc = json.load(handle)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise UnparseableSourceError(f"{path.name}: {exc}") from exc
    return Edition(
        subproject=subproject_of(path),
        text_id=path.stem,
        path=path,
        doc=doc,
        word_count=count_words(doc),
    )


def edition_subprojects(data: Path = paths.DATA) -> list[str]:
    """Annotated-edition subprojects of RIAO and RINAP, in stable order.

    Witness subprojects (sources, scores) are excluded: they are score
    transliterations with no lemmatisation (P-001 section 1).
    """
    out = []
    for project in paths.EDITION_PROJECTS:
        for sub in sorted((data / project).glob("*")):
            if not (sub / paths.CORPUSJSON).is_dir():
                continue
            if sub.name in paths.WITNESS_SUBPROJECTS:
                continue
            out.append(f"{project}/{sub.name}")
    return out


def source_files(data: Path = paths.DATA,
                 subprojects: Sequence[str] | None = None) -> list[Path]:
    if subprojects is None:
        subprojects = edition_subprojects(data)
    files: list[Path] = []
    for sub in subprojects:
        files.extend(sorted((data / sub / paths.CORPUSJSON).glob("*.json")))
    return files


def iter_editions(data: Path = paths.DATA,
                  subprojects: Sequence[str] | None = None,
                  skip_unreadable: bool = False) -> Iterator[Edition]:
    """Yield every edition in scope.

    With skip_unreadable=False (the default) a bad file raises, so a caller
    that has not thought about the three zero-byte files finds out.
    """
    for path in source_files(data, subprojects):
        try:
            yield load_edition(path)
        except SourceError:
            if not skip_unreadable:
                raise


def survey(data: Path = paths.DATA,
           subprojects: Sequence[str] | None = None) -> Survey:
    """Walk the corpus once and report the four cardinalities separately."""
    files = source_files(data, subprojects)
    unreadable: list[Path] = []
    stub_keys: list[str] = []
    keys: list[str] = []
    populated = 0
    for path in files:
        try:
            edition = load_edition(path)
        except SourceError:
            unreadable.append(path)
            continue
        keys.append(edition.key)
        if edition.populated:
            populated += 1
        else:
            stub_keys.append(edition.key)
    return Survey(
        source_files=len(files),
        parseable=len(keys),
        populated=populated,
        stubs=len(stub_keys),
        unreadable=len(unreadable),
        unreadable_paths=tuple(unreadable),
        stub_keys=tuple(stub_keys),
        keys=tuple(keys),
    )


def _main(argv: Sequence[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        prog="python -m oracc_tf.loader",
        description="Report the four RIAO+RINAP edition cardinalities.")
    ap.add_argument("--data", type=Path, default=paths.DATA)
    ap.add_argument("--list-stubs", action="store_true")
    ap.add_argument("--list-unreadable", action="store_true")
    args = ap.parse_args(argv)

    subs = edition_subprojects(args.data)
    result = survey(args.data, subs)
    print(f"subprojects  : {len(subs)}  ({', '.join(subs)})")
    print(result.report())
    if args.list_unreadable:
        print("\nunreadable:")
        for path in result.unreadable_paths:
            print(f"  {subproject_of(path)}:{path.stem}")
    if args.list_stubs:
        print(f"\nstubs ({len(result.stub_keys)}):")
        for key in result.stub_keys:
            print(f"  {key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
