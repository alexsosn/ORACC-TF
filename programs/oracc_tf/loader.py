"""Read ORACC corpusjson editions while preserving source-member evidence.

The loader keeps source membership, parseability and population separate.  A
caller may intentionally skip malformed/empty members, but the source
observation API makes every omission explicit and reproducible instead of
silently losing the member from accounting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterator, Sequence

from . import paths


class SourceError(Exception):
    """Base class for a corpusjson source that cannot become an Edition."""


class EmptySourceError(SourceError):
    """The source file is zero bytes."""


class UnparseableSourceError(SourceError):
    """The source bytes are not a usable corpusjson object."""


class DuplicateSourceIdentityError(SourceError):
    """Two readable members claim the same qualified embedded source identity."""


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
        """Subproject-qualified document identity."""
        return f"{self.subproject}:{self.text_id}"

    @property
    def populated(self) -> bool:
        return self.word_count > 0


@dataclass(frozen=True)
class SourceHazard:
    """Deterministic evidence for one source member that cannot become an Edition."""

    path: Path = field(repr=False, compare=False)
    relative_path: str
    subproject: str
    kind: str
    bytes: int
    sha256: str
    source_id: str | None = None

    def evidence(self) -> dict[str, object]:
        result: dict[str, object] = {
            "relative_path": self.relative_path,
            "subproject": self.subproject,
            "kind": self.kind,
            "bytes": self.bytes,
            "sha256": self.sha256,
        }
        if self.source_id is not None:
            result["source_id"] = self.source_id
        return result


@dataclass(frozen=True)
class ReadableSource:
    """One readable member plus byte-level provenance for its parsed Edition."""

    edition: Edition
    relative_path: str
    bytes: int
    sha256: str


@dataclass(frozen=True)
class Survey:
    """Source/edition cardinalities plus complete typed omission evidence."""

    source_files: int
    parseable: int
    populated: int
    stubs: int
    unreadable: int
    unreadable_paths: tuple[Path, ...]
    stub_keys: tuple[str, ...]
    keys: tuple[str, ...]
    hazards: tuple[SourceHazard, ...] = ()

    def report(self) -> str:
        return (
            f"source files : {self.source_files:>6,}\n"
            f"parseable    : {self.parseable:>6,}   ({self.unreadable} unreadable)\n"
            f"populated    : {self.populated:>6,}\n"
            f"stubs        : {self.stubs:>6,}   valid JSON, no transliteration"
        )


def count_words(doc: dict) -> int:
    """Number of CDL lemma (``l``) nodes in a document."""
    total = 0
    stack = [doc]
    while stack:
        node = stack.pop()
        if node.get("node") == "l":
            total += 1
        stack.extend(node.get("cdl") or [])
    return total


def subproject_of(path: Path, *, data: Path | None = None) -> str:
    """Return stable corpus context for a corpusjson source path.

    With a data root, every path component before the final ``corpusjson``
    directory is retained.  Without a data root the historical two-component
    RIAO/RINAP fallback is preserved for direct ``load_edition()`` callers.
    """
    path = Path(path)
    if data is not None:
        try:
            relative = path.resolve().relative_to(Path(data).resolve())
        except ValueError as exc:
            raise SourceError(f"source path is outside data root: {path}") from exc
        parts = relative.parts
        try:
            i = len(parts) - 1 - parts[::-1].index(paths.CORPUSJSON)
        except ValueError:
            return relative.parent.as_posix()
        context = parts[:i]
        return "/".join(context) if context else relative.parent.name

    parts = path.resolve().parts
    try:
        i = len(parts) - 1 - parts[::-1].index(paths.CORPUSJSON)
    except ValueError:
        return path.parent.name
    return "/".join(parts[i - 2:i])


def _relative_path(path: Path, data: Path | None) -> str:
    if data is None:
        return path.name
    try:
        return path.resolve().relative_to(Path(data).resolve()).as_posix()
    except ValueError as exc:
        raise SourceError(f"source path is outside data root: {path}") from exc


def _hazard(
    *,
    path: Path,
    data: Path | None,
    payload: bytes,
    kind: str,
    source_id: str | None = None,
) -> SourceHazard:
    return SourceHazard(
        path=path,
        relative_path=_relative_path(path, data),
        subproject=subproject_of(path, data=data),
        kind=kind,
        bytes=len(payload),
        sha256=sha256(payload).hexdigest(),
        source_id=source_id,
    )


def observe_source(path: Path | str, *, data: Path | None = None) -> ReadableSource | SourceHazard:
    """Read and classify one source member exactly once.

    Filename/path remains provenance only.  A readable scholarly identity comes
    exclusively from a non-empty embedded JSON ``textid`` and is preserved
    verbatim rather than normalized.
    """
    path = Path(path)
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise SourceError(f"cannot read source bytes: {path}") from exc

    if not payload:
        return _hazard(path=path, data=data, payload=payload, kind="empty-file")

    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return _hazard(path=path, data=data, payload=payload, kind="invalid-utf8")

    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return _hazard(path=path, data=data, payload=payload, kind="invalid-json")

    if not isinstance(value, dict):
        return _hazard(path=path, data=data, payload=payload, kind="non-object-json")

    source_id = value.get("textid")
    if not isinstance(source_id, str) or not source_id.strip():
        return _hazard(path=path, data=data, payload=payload, kind="missing-source-id")

    edition = Edition(
        subproject=subproject_of(path, data=data),
        text_id=source_id,
        path=path,
        doc=value,
        word_count=count_words(value),
    )
    return ReadableSource(
        edition=edition,
        relative_path=_relative_path(path, data),
        bytes=len(payload),
        sha256=sha256(payload).hexdigest(),
    )


def _raise_hazard(hazard: SourceHazard) -> None:
    if hazard.kind == "empty-file":
        raise EmptySourceError(
            f"{hazard.path.name}: zero-byte source file ({hazard.path})"
        )
    raise UnparseableSourceError(
        f"{hazard.path.name}: source hazard {hazard.kind} ({hazard.path})"
    )


def load_edition(path: Path) -> Edition:
    """Parse one corpusjson file, failing closed on any source hazard."""
    observation = observe_source(path)
    if isinstance(observation, SourceHazard):
        _raise_hazard(observation)
    return observation.edition


def edition_subprojects(data: Path = paths.DATA) -> list[str]:
    """Annotated-edition subprojects of RIAO and RINAP, in stable order."""
    out = []
    for project in paths.EDITION_PROJECTS:
        for sub in sorted((Path(data) / project).glob("*")):
            if not (sub / paths.CORPUSJSON).is_dir():
                continue
            if sub.name in paths.WITNESS_SUBPROJECTS:
                continue
            out.append(f"{project}/{sub.name}")
    return out


def source_files(
    data: Path = paths.DATA,
    subprojects: Sequence[str] | None = None,
) -> list[Path]:
    data = Path(data)
    if subprojects is None:
        subprojects = edition_subprojects(data)
    files: list[Path] = []
    for sub in subprojects:
        files.extend(sorted((data / sub / paths.CORPUSJSON).glob("*.json")))
    return files


def iter_source_observations(
    data: Path = paths.DATA,
    subprojects: Sequence[str] | None = None,
) -> Iterator[ReadableSource | SourceHazard]:
    """Yield every source member in existing stable file order with audit evidence."""
    data = Path(data)
    seen: dict[str, str] = {}
    for path in source_files(data, subprojects):
        observation = observe_source(path, data=data)
        if isinstance(observation, ReadableSource):
            key = observation.edition.key
            previous_path = seen.get(key)
            if previous_path is not None:
                raise DuplicateSourceIdentityError(
                    f"duplicate embedded source identity {key!r}: "
                    f"{previous_path!r} and {observation.relative_path!r}"
                )
            seen[key] = observation.relative_path
        yield observation


def iter_editions(
    data: Path = paths.DATA,
    subprojects: Sequence[str] | None = None,
    skip_unreadable: bool = False,
) -> Iterator[Edition]:
    """Compatibility iterator over readable editions.

    ``skip_unreadable=False`` remains fail-fast.  When skipping is intentional,
    callers that need complete omission evidence should consume
    :func:`iter_source_observations` directly.
    """
    for observation in iter_source_observations(data, subprojects):
        if isinstance(observation, SourceHazard):
            if not skip_unreadable:
                _raise_hazard(observation)
            continue
        yield observation.edition


def canonical_hazard_bytes(hazards: Sequence[SourceHazard]) -> bytes:
    """Canonical machine-readable omission evidence with no checkout-local paths."""
    ordered = sorted(
        hazards,
        key=lambda hazard: (
            hazard.relative_path,
            hazard.subproject,
            hazard.kind,
            hazard.bytes,
            hazard.sha256,
            hazard.source_id is not None,
            hazard.source_id or "",
        ),
    )
    report = {
        "schema_version": 1,
        "hazards": [hazard.evidence() for hazard in ordered],
    }
    return (
        json.dumps(
            report,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def survey(
    data: Path = paths.DATA,
    subprojects: Sequence[str] | None = None,
) -> Survey:
    """Walk the corpus once and report source/readable/population cardinalities."""
    hazards: list[SourceHazard] = []
    stub_keys: list[str] = []
    keys: list[str] = []
    populated = 0
    source_count = 0

    for observation in iter_source_observations(data, subprojects):
        source_count += 1
        if isinstance(observation, SourceHazard):
            hazards.append(observation)
            continue
        edition = observation.edition
        keys.append(edition.key)
        if edition.populated:
            populated += 1
        else:
            stub_keys.append(edition.key)

    return Survey(
        source_files=source_count,
        parseable=len(keys),
        populated=populated,
        stubs=len(stub_keys),
        unreadable=len(hazards),
        unreadable_paths=tuple(hazard.path for hazard in hazards),
        stub_keys=tuple(stub_keys),
        keys=tuple(keys),
        hazards=tuple(hazards),
    )


def _main(argv: Sequence[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        prog="python -m oracc_tf.loader",
        description="Report RIAO+RINAP source and edition cardinalities.",
    )
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
        for hazard in result.hazards:
            print(f"  {hazard.subproject}:{hazard.relative_path} [{hazard.kind}]")
    if args.list_stubs:
        print(f"\nstubs ({len(result.stub_keys)}):")
        for key in result.stub_keys:
            print(f"  {key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
