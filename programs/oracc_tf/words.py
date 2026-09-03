"""Source-faithful word layer for P-001 M2.

A word is an ORACC ``node='l'`` object plus the semantic sign slots selected by
M1. Raw GDL tree leaves are never counted independently here: composite signs,
rendering references and operators have already been resolved by
:mod:`oracc_tf.gdl`.

Slot ordinals are 1-based to match Text-Fabric node numbers. A word span is the
half-open interval ``[slot_start, slot_end)``; its TF slot ids are therefore
``range(slot_start, slot_end)``. Callers can pass a non-default start slot to
continue numbering across documents in the joined corpus.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from . import gdl, loader, paths


class InvalidWordSource(ValueError):
    """A source object cannot be represented as an M2 word record."""


@dataclass(frozen=True)
class WordRecord:
    """One ORACC word and its contiguous semantic sign span."""

    source_id: str
    ref: str | None
    frag: str | None
    form: str | None
    lang: str | None
    cf: str | None
    gw: str | None
    sense: str | None
    norm: str | None
    pos: str | None
    epos: str | None
    inst: str | None
    sig: str | None
    lemmaknown: int
    slot_start: int
    slot_end: int
    signs: tuple[gdl.ClassifiedGDL, ...]
    source: Mapping[str, object] = field(repr=False, compare=False)
    features: Mapping[str, object] = field(repr=False, compare=False)

    @property
    def sign_count(self) -> int:
        return len(self.signs)

    @property
    def slot_ids(self) -> range:
        """The exact 1-based slot ids occupied by this word."""
        return range(self.slot_start, self.slot_end)


@dataclass(frozen=True)
class WordCensus:
    """Whole-corpus M2 word/sign accounting."""

    words: int
    signs: int
    lemmatised: int
    unlemmatised: int
    zero_sign_words: int
    span_errors: int

    def report(self) -> str:
        return (
            f"words          : {self.words:>8,}\n"
            f"signs          : {self.signs:>8,}\n"
            f"lemmatised     : {self.lemmatised:>8,}\n"
            f"unlemmatised   : {self.unlemmatised:>8,}\n"
            f"zero-sign words: {self.zero_sign_words:>8,}\n"
            f"span errors    : {self.span_errors:>8,}"
        )


def _optional_str(mapping: Mapping[str, object], key: str, where: str) -> str | None:
    value = mapping.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise InvalidWordSource(
            f"{where}: {key!r} is {type(value).__name__}, expected string"
        )
    return value


def _required_str(mapping: Mapping[str, object], key: str, where: str) -> str:
    value = _optional_str(mapping, key, where)
    if not value:
        raise InvalidWordSource(f"{where}: missing non-empty {key!r}")
    return value


def from_source(node: Mapping[str, object], *, start_slot: int) -> WordRecord:
    """Convert one ORACC ``l`` node into a word record.

    ``start_slot`` is the first 1-based TF-compatible sign ordinal available to
    this word. The returned ``slot_end`` can be passed directly to the next
    word, making overlap/gap bugs explicit at the API boundary.
    """
    if not isinstance(node, Mapping) or node.get("node") != "l":
        raise InvalidWordSource("word source must be an object with node='l'")
    if not isinstance(start_slot, int) or isinstance(start_slot, bool) or start_slot < 1:
        raise InvalidWordSource("start_slot must be a positive 1-based integer")

    source_id = _required_str(node, "id", "word")
    features_obj = node.get("f")
    if features_obj is None:
        features: Mapping[str, object] = {}
    elif isinstance(features_obj, Mapping):
        features = features_obj
    else:
        raise InvalidWordSource(
            f"{source_id}: 'f' is {type(features_obj).__name__}, expected object"
        )

    gdl_obj = features.get("gdl")
    if gdl_obj is None:
        entries: Sequence[Mapping[str, object]] = ()
    elif isinstance(gdl_obj, Sequence) and not isinstance(gdl_obj, (str, bytes, bytearray)):
        entries = gdl_obj  # gdl validates each child object and fails closed.
    else:
        raise InvalidWordSource(
            f"{source_id}: 'gdl' is {type(gdl_obj).__name__}, expected list"
        )

    signs = tuple(gdl.signs(entries, word_id=source_id))
    lexical_keys = ("cf", "gw", "sense", "norm")
    has_analysis = (
        any(features.get(key) is not None for key in lexical_keys)
        or node.get("sig") is not None
    )

    return WordRecord(
        source_id=source_id,
        ref=_optional_str(node, "ref", source_id),
        frag=_optional_str(node, "frag", source_id),
        form=_optional_str(features, "form", source_id),
        lang=_optional_str(features, "lang", source_id),
        cf=_optional_str(features, "cf", source_id),
        gw=_optional_str(features, "gw", source_id),
        sense=_optional_str(features, "sense", source_id),
        norm=_optional_str(features, "norm", source_id),
        pos=_optional_str(features, "pos", source_id),
        epos=_optional_str(features, "epos", source_id),
        inst=_optional_str(node, "inst", source_id),
        sig=_optional_str(node, "sig", source_id),
        lemmaknown=int(has_analysis),
        slot_start=start_slot,
        slot_end=start_slot + len(signs),
        signs=signs,
        source=node,
        features=features,
    )


def source_words(doc: Mapping[str, object]) -> Iterator[Mapping[str, object]]:
    """Yield source ``l`` nodes in document order, not stack/LIFO order."""
    if not isinstance(doc, Mapping):
        raise InvalidWordSource("document root must be an object")

    def walk(node: Mapping[str, object], where: str) -> Iterator[Mapping[str, object]]:
        if node.get("node") == "l":
            yield node

        children_obj = node.get("cdl")
        if children_obj is None:
            return
        if not isinstance(children_obj, list):
            raise InvalidWordSource(
                f"{where}: 'cdl' is {type(children_obj).__name__}, expected list"
            )
        for index, child in enumerate(children_obj):
            if not isinstance(child, Mapping):
                raise InvalidWordSource(
                    f"{where}/cdl[{index}]: child is {type(child).__name__}, expected object"
                )
            yield from walk(child, f"{where}/cdl[{index}]")

    yield from walk(doc, "document")


def iter_words(
    doc: Mapping[str, object], *, start_slot: int = 1
) -> Iterator[WordRecord]:
    """Yield word records in source order with gap-free sequential spans."""
    if not isinstance(start_slot, int) or isinstance(start_slot, bool) or start_slot < 1:
        raise InvalidWordSource("start_slot must be a positive 1-based integer")

    next_slot = start_slot
    for node in source_words(doc):
        word = from_source(node, start_slot=next_slot)
        yield word
        next_slot = word.slot_end


def census(data: Path = paths.DATA) -> WordCensus:
    """Measure the M2 word layer over the joined RIAO + RINAP corpus.

    Slot numbering continues across document boundaries exactly as it will in
    the joined Text-Fabric dataset. The direct source word count remains an
    independent M0 measurement and is compared by the M2 corpus test.
    """
    word_count = 0
    lemmatised = 0
    unlemmatised = 0
    zero_sign_words = 0
    span_errors = 0
    next_slot = 1

    for edition in loader.iter_editions(data, skip_unreadable=True):
        for word in iter_words(edition.doc, start_slot=next_slot):
            if word.slot_start != next_slot or word.slot_end < word.slot_start:
                span_errors += 1
            word_count += 1
            if word.lemmaknown:
                lemmatised += 1
            else:
                unlemmatised += 1
            if word.sign_count == 0:
                zero_sign_words += 1
            next_slot = word.slot_end

    return WordCensus(
        words=word_count,
        signs=next_slot - 1,
        lemmatised=lemmatised,
        unlemmatised=unlemmatised,
        zero_sign_words=zero_sign_words,
        span_errors=span_errors,
    )
