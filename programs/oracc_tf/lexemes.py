"""Canonical lexeme identity and compound-word linking for P-001 M4.

ORACC's word layer carries two related but deliberately distinct encodings:

* ``inst`` describes occurrence slots.  Compound orthographic forms can repeat
  the same slot many times, so its arity is not a word→lex degree.
* ``sig`` describes canonical lexical analyses and includes project, language,
  written form, sense, epos and normalisation.  Only ``(lang, cf, gw, pos)``
  belongs to lexeme identity; the rest remains occurrence provenance.

The module preserves both views instead of deriving one from the other.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from . import loader, paths, words


class LexemeError(ValueError):
    """Base class for malformed lexical source data."""


class InvalidInst(LexemeError):
    """Raised when an ORACC ``inst`` string cannot be parsed losslessly."""


class InvalidSignature(LexemeError):
    """Raised when an ORACC occurrence ``sig`` cannot be parsed."""


class DuplicateWordId(LexemeError):
    """Raised when one source document repeats an ``l`` node id."""


@dataclass(frozen=True, order=True)
class LexemeKey:
    """Project-independent lexical identity used for TF lex nodes."""

    lang: str
    cf: str
    gw: str
    pos: str


@dataclass(frozen=True)
class InstSlot:
    """One top-level ``&``-separated occurrence slot from ``inst``."""

    raw: str
    form: str
    gw: str
    sense: str | None
    pos: str
    norm: str | None
    coform: bool = False


@dataclass(frozen=True)
class SignatureAnalysis:
    """One canonical analysis component from a full ORACC ``sig``."""

    raw: str
    project: str
    lang: str
    form: str
    cf: str
    gw: str
    sense: str | None
    pos: str
    epos: str | None
    norm: str | None

    @property
    def key(self) -> LexemeKey:
        return LexemeKey(self.lang, self.cf, self.gw, self.pos)


@dataclass(frozen=True)
class DocumentLexemeIndex:
    """Lexical view of one edition without changing its word cardinality."""

    lexemes: frozenset[LexemeKey]
    word_to_lex: Mapping[str, tuple[LexemeKey, ...]]
    inst_slots: Mapping[str, tuple[InstSlot, ...]]
    word_sigs: Mapping[str, str | None]
    word_count: int


@dataclass(frozen=True)
class LexemeCensus:
    words: int
    lexemes: int
    cross_language_triples: int
    max_inst_slots: int
    max_word_lex_degree: int

    def report(self) -> str:
        return "\n".join((
            f"words                   : {self.words:>8,}",
            f"lexemes                 : {self.lexemes:>8,}",
            f"cross-language triples  : {self.cross_language_triples:>8,}",
            f"max inst slots          : {self.max_inst_slots:>8,}",
            f"max word→lex degree     : {self.max_word_lex_degree:>8,}",
        ))


def _split_top_level(text: str, separator: str) -> tuple[str, ...]:
    """Split on *separator* outside square brackets, preserving empty text.

    Glosses are bracketed and may themselves contain punctuation.  A raw
    ``str.split('&')`` would therefore make the parser dependent on gloss
    vocabulary rather than ORACC syntax.
    """
    if not separator:
        raise ValueError("separator must be non-empty")

    out: list[str] = []
    start = 0
    depth = 0
    i = 0
    while i < len(text):
        char = text[i]
        if char == "[":
            depth += 1
            i += 1
            continue
        if char == "]":
            if depth == 0:
                raise LexemeError(f"unmatched ']' in {text!r}")
            depth -= 1
            i += 1
            continue
        if depth == 0 and text.startswith(separator, i):
            out.append(text[start:i])
            i += len(separator)
            start = i
            continue
        i += 1

    if depth:
        raise LexemeError(f"unclosed '[' in {text!r}")
    out.append(text[start:])
    return tuple(out)


def _analysis_parts(text: str, *, source: str) -> tuple[str, str, str | None, str]:
    """Return form/cf, gw, sense and the suffix after the closing bracket.

    ORACC uses an empty bracket pair for some valid occurrence analyses (for
    example ``Zarpanitu[]DN$Zer-banitum``).  Empty ``gw`` is therefore
    preserved as source data rather than treated as malformed syntax.
    """
    left = text.find("[")
    if left <= 0:
        exc = InvalidInst if source == "inst" else InvalidSignature
        raise exc(f"{source} analysis lacks form/cf or '[': {text!r}")

    depth = 0
    right = -1
    for i in range(left, len(text)):
        if text[i] == "[":
            depth += 1
        elif text[i] == "]":
            depth -= 1
            if depth == 0:
                right = i
                break
            if depth < 0:
                break
    if right < 0:
        exc = InvalidInst if source == "inst" else InvalidSignature
        raise exc(f"{source} analysis has unclosed gloss: {text!r}")

    head = text[:left]
    gloss = text[left + 1:right]
    suffix = text[right + 1:]
    if "//" in gloss:
        gw, sense = gloss.split("//", 1)
    else:
        gw, sense = gloss, None
    return head, gw, sense, suffix


def parse_inst(inst: str | None) -> tuple[InstSlot, ...]:
    """Parse top-level ORACC ``inst`` slots without collapsing repetition."""
    if not inst:
        return ()

    slots: list[InstSlot] = []
    for raw in _split_top_level(inst, "&"):
        if not raw:
            raise InvalidInst(f"empty inst slot in {inst!r}")
        coform = raw.startswith("+")
        body = raw[1:] if coform else raw
        form, gw, sense, suffix = _analysis_parts(body, source="inst")
        if "$" in suffix:
            pos, norm = suffix.split("$", 1)
        else:
            pos, norm = suffix, None
        if not form or not pos:
            raise InvalidInst(f"inst slot lacks form or pos: {raw!r}")
        slots.append(InstSlot(
            raw=raw,
            form=form,
            gw=gw,
            sense=sense,
            pos=pos,
            norm=norm,
            coform=coform,
        ))
    return tuple(slots)


def parse_sig(sig: str | None) -> tuple[SignatureAnalysis, ...]:
    """Parse distinct canonical analyses from an ORACC occurrence signature."""
    if not sig:
        return ()

    analyses: list[SignatureAnalysis] = []
    for raw in _split_top_level(sig, "&&"):
        if not raw.startswith("@"):
            raise InvalidSignature(f"signature component lacks '@': {raw!r}")
        try:
            prefix, body = raw[1:].split("=", 1)
            project_lang, form = prefix.split(":", 1)
            project, lang = project_lang.rsplit("%", 1)
        except ValueError as exc:
            raise InvalidSignature(f"malformed signature prefix: {raw!r}") from exc

        cf, gw, sense, suffix = _analysis_parts(body, source="sig")
        if "$" in suffix:
            poses, norm = suffix.split("$", 1)
        else:
            poses, norm = suffix, None
        if "'" in poses:
            pos, epos = poses.split("'", 1)
        else:
            pos, epos = poses, None
        if not project or not lang or not cf or not pos:
            raise InvalidSignature(f"signature lacks project/lang/cf/pos: {raw!r}")

        analyses.append(SignatureAnalysis(
            raw=raw,
            project=project,
            lang=lang,
            form=form,
            cf=cf,
            gw=gw,
            sense=sense,
            pos=pos,
            epos=epos,
            norm=norm,
        ))
    return tuple(analyses)


def _direct_key(word: words.WordRecord) -> LexemeKey | None:
    if all((word.lang, word.cf, word.gw, word.pos)):
        return LexemeKey(word.lang or "", word.cf or "", word.gw or "", word.pos or "")
    return None


def keys_for_word(word: words.WordRecord) -> tuple[LexemeKey, ...]:
    """Return distinct canonical lexeme links for one source word.

    A full ``sig`` is authoritative for a COF head because it lists all
    distinct analyses even when ``inst`` repeats one of them many times.
    COF tails normally carry ``tail-sig`` instead.  Direct M2 fields are the
    fallback for source words without either signature.
    """
    raw_sig = word.sig
    if raw_sig:
        candidates = [analysis.key for analysis in parse_sig(raw_sig)]
    else:
        tail_sig = word.source.get("tail-sig")
        if isinstance(tail_sig, str) and tail_sig:
            candidates = [analysis.key for analysis in parse_sig(tail_sig)]
        else:
            direct = _direct_key(word)
            candidates = [] if direct is None else [direct]

    distinct: list[LexemeKey] = []
    seen: set[LexemeKey] = set()
    for key in candidates:
        if key not in seen:
            seen.add(key)
            distinct.append(key)
    return tuple(distinct)


def index_document(doc: Mapping[str, object]) -> DocumentLexemeIndex:
    """Build the lexeme view of one document in source word order."""
    word_to_lex: dict[str, tuple[LexemeKey, ...]] = {}
    inst_slots: dict[str, tuple[InstSlot, ...]] = {}
    word_sigs: dict[str, str | None] = {}
    lexeme_set: set[LexemeKey] = set()

    count = 0
    for word in words.iter_words(doc):
        if word.source_id in word_to_lex:
            raise DuplicateWordId(f"duplicate word id {word.source_id!r}")
        count += 1
        slots = parse_inst(word.inst)
        links = keys_for_word(word)
        inst_slots[word.source_id] = slots
        word_to_lex[word.source_id] = links
        word_sigs[word.source_id] = word.sig
        lexeme_set.update(links)

    return DocumentLexemeIndex(
        lexemes=frozenset(lexeme_set),
        word_to_lex=word_to_lex,
        inst_slots=inst_slots,
        word_sigs=word_sigs,
        word_count=count,
    )


def census(data: Path = paths.DATA) -> LexemeCensus:
    """Measure joined-corpus lexical identity and compound arities."""
    all_lexemes: set[LexemeKey] = set()
    triple_langs: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    word_count = 0
    max_inst_slots = 0
    max_word_lex_degree = 0

    for edition in loader.iter_editions(data, skip_unreadable=True):
        index = index_document(edition.doc)
        word_count += index.word_count
        all_lexemes.update(index.lexemes)
        for key in index.lexemes:
            triple_langs[(key.cf, key.gw, key.pos)].add(key.lang)
        if index.inst_slots:
            max_inst_slots = max(max_inst_slots, max(map(len, index.inst_slots.values())))
        if index.word_to_lex:
            max_word_lex_degree = max(
                max_word_lex_degree,
                max(map(len, index.word_to_lex.values())),
            )

    return LexemeCensus(
        words=word_count,
        lexemes=len(all_lexemes),
        cross_language_triples=sum(len(langs) > 1 for langs in triple_langs.values()),
        max_inst_slots=max_inst_slots,
        max_word_lex_degree=max_word_lex_degree,
    )
