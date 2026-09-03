"""Semantic GDL classification for P-001 M1.

ORACC's GDL is a tree, but tree position alone does not determine whether an
object occupies a textual sign position. In particular, numerals, qualified
signs and compounds carry their sign data on a parent that also has children.
Those parents are slots; their children describe rendering/qualification and
must not become extra slots.

A qualified grapheme whose ``q`` wrapper has no own ``utf8`` is the important
exception to the simple parent-slot rule: ORACC encodes it as a sign value
followed by a sign name. The value child is qualification metadata and the
sign-name child supplies the single textual position.

Every object reached by :func:`classify_tree` receives one of four explicit
dispositions. Unknown leaves raise :class:`UnknownGDLShape`, making upstream
schema drift a build failure rather than silent data loss.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterator, Mapping, Sequence

from . import loader, paths


CHILD_KEYS = ("group", "seq", "qualified", "mods")
_PATH_PART = re.compile(r"/(gdl|group|seq|qualified|mods)\[(\d+)\]")


class Disposition(str, Enum):
    """Semantic role of one GDL object."""

    SLOT = "slot"
    STRUCTURAL = "structural"
    MODIFIER = "modifier"
    RENDERING = "rendering"


class UnknownGDLShape(ValueError):
    """A GDL object has no known semantic disposition."""


@dataclass(frozen=True)
class ClassifiedGDL:
    """One source GDL object plus its semantic disposition and source path."""

    disposition: Disposition
    value: Mapping[str, object]
    src_path: str


@dataclass(frozen=True)
class GDLCensus:
    """Corpus-wide count of the four semantic GDL dispositions."""

    slot: int
    structural: int
    modifier: int
    rendering: int
    unknown: int = 0

    @property
    def total(self) -> int:
        return self.slot + self.structural + self.modifier + self.rendering + self.unknown

    def report(self) -> str:
        return (
            f"slot       : {self.slot:>8,}\n"
            f"structural : {self.structural:>8,}\n"
            f"modifier   : {self.modifier:>8,}\n"
            f"rendering  : {self.rendering:>8,}\n"
            f"total      : {self.total:>8,}"
        )


def _children(
    obj: Mapping[str, object], src_path: str
) -> Iterator[tuple[str, int, Mapping[str, object]]]:
    for key in CHILD_KEYS:
        if key not in obj:
            continue
        value = obj[key]
        if not isinstance(value, list):
            raise UnknownGDLShape(
                f"{src_path}: child field {key!r} is {type(value).__name__}, expected list"
            )
        for index, child in enumerate(value):
            if not isinstance(child, dict):
                raise UnknownGDLShape(
                    f"{src_path}/{key}[{index}]: GDL child is "
                    f"{type(child).__name__}, expected object"
                )
            yield key, index, child


def _normal_disposition(obj: Mapping[str, object], src_path: str) -> Disposition:
    # A sign-bearing parent wins over its children. This is the crucial M1
    # rule for n/q/c composite signs that carry their own Unicode.
    if obj.get("utf8"):
        return Disposition.SLOT

    # v/s/x are positional grapheme objects even without Unicode. In ORACC's
    # JSON, `o` is overloaded: a real compound operator is a standalone
    # {"o": ...} object, while a grapheme can also carry `o` as auxiliary
    # markup/original-form metadata. Test sign identity before interpreting
    # `o` (or `r`) as an object kind.
    if any(key in obj for key in ("v", "s", "x")):
        return Disposition.SLOT

    # A child-bearing object without its own Unicode is a structural wrapper:
    # logo, determinative, alternation, ligature, bare group, or a no-utf8 q
    # wrapper. The q case gets child-specific suppression in classify_tree().
    if any(key in obj for key in CHILD_KEYS):
        list(_children(obj, src_path))
        return Disposition.STRUCTURAL

    # Rendering references and compound operators are explicit non-sign
    # leaves only after sign-bearing shapes have been ruled out.
    if "r" in obj:
        return Disposition.RENDERING
    if "o" in obj:
        return Disposition.MODIFIER

    raise UnknownGDLShape(f"{src_path}: unknown GDL shape {dict(obj)!r}")


def _suppressed_disposition(
    obj: Mapping[str, object], src_path: str
) -> Disposition:
    """Classify a descendant internal to a composite sign slot.

    Suppression changes the disposition of known sign-like descendants from
    slot to modifier, but it must not turn arbitrary schema drift into a valid
    modifier. Unknown leaves therefore fail here just as they do at the normal
    tree level.
    """
    if any(key in obj for key in ("v", "s", "x")):
        return Disposition.MODIFIER
    if any(key in obj for key in CHILD_KEYS):
        return Disposition.MODIFIER
    if "r" in obj:
        return Disposition.RENDERING
    if "o" in obj:
        return Disposition.MODIFIER
    raise UnknownGDLShape(f"{src_path}: unknown nested GDL shape {dict(obj)!r}")


def classify_tree(
    entries: Sequence[Mapping[str, object]], *, word_id: str
) -> Iterator[ClassifiedGDL]:
    """Classify every object in a word's GDL tree."""
    if not isinstance(entries, (list, tuple)):
        raise TypeError("entries must be a GDL list/tuple")
    if not word_id:
        raise ValueError("word_id is required for auditable src_path values")

    def walk(
        obj: Mapping[str, object], src_path: str, suppressed: bool
    ) -> Iterator[ClassifiedGDL]:
        if not isinstance(obj, dict):
            raise UnknownGDLShape(
                f"{src_path}: GDL item is {type(obj).__name__}, expected object"
            )

        if suppressed:
            disposition = _suppressed_disposition(obj, src_path)
        else:
            disposition = _normal_disposition(obj, src_path)

        yield ClassifiedGDL(
            disposition=disposition, value=obj, src_path=src_path
        )

        # Descendants of a sign-bearing parent are internal descriptions of
        # that sign, not additional textual positions.
        suppress_children = suppressed or disposition == Disposition.SLOT

        # ORACC q is one qualified grapheme: value + sign name. If the wrapper
        # has no own Unicode, the value child must not become a second slot;
        # the sign-name child is classified normally and supplies the position.
        no_utf8_q = (
            not suppressed
            and disposition == Disposition.STRUCTURAL
            and "q" in obj
            and not obj.get("utf8")
            and "qualified" in obj
        )
        if no_utf8_q:
            qualified = obj.get("qualified")
            if not isinstance(qualified, list) or len(qualified) != 2:
                raise UnknownGDLShape(
                    f"{src_path}: no-utf8 qualified grapheme must contain "
                    "exactly value and sign-name children"
                )

        for key, index, child in _children(obj, src_path):
            child_path = f"{src_path}/{key}[{index}]"
            child_suppressed = suppress_children
            if no_utf8_q and key == "qualified" and index == 0:
                child_suppressed = True
            yield from walk(child, child_path, child_suppressed)

    for index, obj in enumerate(entries):
        if not isinstance(obj, dict):
            raise UnknownGDLShape(
                f"{word_id}/gdl[{index}]: GDL item is {type(obj).__name__}, expected object"
            )
        yield from walk(obj, f"{word_id}/gdl[{index}]", False)


def signs(
    entries: Sequence[Mapping[str, object]], *, word_id: str
) -> Iterator[ClassifiedGDL]:
    """Yield only textual sign slots while preserving their source paths."""
    for item in classify_tree(entries, word_id=word_id):
        if item.disposition == Disposition.SLOT:
            yield item


def resolve_src_path(
    entries: Sequence[Mapping[str, object]], src_path: str, *, word_id: str
) -> Mapping[str, object]:
    """Resolve a ``word-id/gdl[i]/...`` path back to the original GDL object."""
    prefix = word_id
    if not src_path.startswith(prefix):
        raise ValueError(f"src_path belongs to a different word: {src_path!r}")
    remainder = src_path[len(prefix):]
    parts = list(_PATH_PART.finditer(remainder))
    if not parts or parts[0].group(1) != "gdl":
        raise ValueError(f"invalid GDL src_path: {src_path!r}")
    if "".join(match.group(0) for match in parts) != remainder:
        raise ValueError(f"invalid GDL src_path: {src_path!r}")

    current: object = entries
    for pos, match in enumerate(parts):
        key = match.group(1)
        index = int(match.group(2))
        if pos == 0:
            if key != "gdl" or not isinstance(current, (list, tuple)):
                raise ValueError(f"invalid GDL src_path: {src_path!r}")
            try:
                current = current[index]
            except IndexError as exc:
                raise ValueError(f"src_path index out of range: {src_path!r}") from exc
            continue

        if not isinstance(current, Mapping) or key not in current:
            raise ValueError(f"src_path does not resolve: {src_path!r}")
        children = current[key]
        if not isinstance(children, list):
            raise ValueError(f"src_path child is not a list: {src_path!r}")
        try:
            current = children[index]
        except IndexError as exc:
            raise ValueError(f"src_path index out of range: {src_path!r}") from exc

    if not isinstance(current, Mapping):
        raise ValueError(f"src_path does not resolve to an object: {src_path!r}")
    return current


def _words(doc: Mapping[str, object]) -> Iterator[Mapping[str, object]]:
    stack = [doc]
    while stack:
        node = stack.pop()
        if node.get("node") == "l":
            yield node
        cdl = node.get("cdl") or []
        if not isinstance(cdl, list):
            raise ValueError("CDL child field must be a list")
        stack.extend(cdl)


def census(data: Path = paths.DATA) -> GDLCensus:
    """Compute the M1 four-way disposition census over RIAO + RINAP editions.

    Unknown GDL shapes are intentionally not swallowed: ``classify_tree``
    raises, so schema drift fails the corpus build.
    """
    counts: Counter[Disposition] = Counter()
    for edition in loader.iter_editions(data, skip_unreadable=True):
        for word in _words(edition.doc):
            word_id = word.get("id")
            if not isinstance(word_id, str) or not word_id:
                raise ValueError(f"{edition.key}: word without source id")
            features = word.get("f") or {}
            entries = features.get("gdl") or []
            for item in classify_tree(entries, word_id=word_id):
                counts[item.disposition] += 1

    return GDLCensus(
        slot=counts[Disposition.SLOT],
        structural=counts[Disposition.STRUCTURAL],
        modifier=counts[Disposition.MODIFIER],
        rendering=counts[Disposition.RENDERING],
    )
