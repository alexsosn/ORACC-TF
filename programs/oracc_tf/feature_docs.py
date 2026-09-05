"""Canonical one-line descriptions for emitted Text-Fabric features.

P-003 makes TF metadata the source of truth for feature meaning.  Keep these
statements concise, source-facing, and free of corpus statistics; generated
reference pages derive their prose from these descriptions rather than
maintaining a second feature glossary in Markdown.
"""

from __future__ import annotations


FEATURE_DESCRIPTIONS: dict[str, str] = {
    # Warp
    "otype": "Text-Fabric node type; sign is the slot type.",
    "oslots": "Text-Fabric slot membership for each non-slot node.",
    # Shared/source identity
    "document_key": "Source-qualified ORACC edition identity in subproject:Q form.",
    "source_id": "Source object identifier preserved from ORACC input.",
    "text_id": "ORACC Q-number; not globally unique across subprojects.",
    "subproject": "ORACC subproject path that qualifies the edition identity.",
    "ref": "Source reference string attached to the ORACC entity.",
    "label": "Source label attached to a physical or structural section marker.",
    # Sign slots / GDL
    "word_id": "Source word identifier that owns this sign slot.",
    "src_path": "Resolvable path to the source GDL object from which the sign slot was classified.",
    "utf8": "Cuneiform Unicode rendering supplied by the source GDL object when available.",
    "readingu": "OldBabylonian-compatible alias of utf8 for a sign's cuneiform Unicode reading.",
    "sign_json": "Canonical JSON serialization of the preserved source GDL sign object.",
    "gdl_id": "Source GDL sign identifier when present.",
    "gdl_form": "Source GDL form value for the sign when present.",
    "gdl_sexified": "Source GDL sexified numeral/form value when present.",
    # Document/catalogue
    "document": "Source-qualified ORACC document identity in subproject:Q form.",
    "populated": "1 when the source edition contains corpus words; 0 for a metadata-only stub.",
    "catalogue_present": "1 when exactly one catalogue record joined to the source-qualified edition.",
    "catalogue_json": "Canonical JSON serialization of the joined source catalogue record.",
    "license": "Raw source licence string preserved without normalization.",
    "license_url": "Raw source licence URL preserved without normalization.",
    "license_type": "Raw explicit source licence-type field; never inferred when absent.",
    "designation": "Catalogue designation preserved from ORACC metadata.",
    "genre": "Catalogue genre preserved from ORACC metadata.",
    "subgenre": "Catalogue subgenre preserved from ORACC metadata.",
    "period": "Catalogue period preserved from ORACC metadata.",
    "provenience": "Catalogue provenience preserved from ORACC metadata.",
    "language": "Catalogue language value preserved from ORACC metadata.",
    "supergenre": "Catalogue supergenre preserved from ORACC metadata.",
    "ruler": "Catalogue ruler value preserved from ORACC metadata.",
    "object_type": "Catalogue object-type value preserved from ORACC metadata.",
    "material": "Catalogue material value preserved from ORACC metadata.",
    "script": "Catalogue script value preserved from ORACC metadata.",
    "exemplars": "Catalogue exemplar information preserved from ORACC metadata.",
    "primary_publication": "Catalogue primary-publication value preserved from ORACC metadata.",
    "pleiades_id": "Catalogue Pleiades identifier preserved from ORACC metadata.",
    "pleiades_coord": "Catalogue Pleiades coordinate value preserved from ORACC metadata.",
    "cdli_id": "Catalogue CDLI identifier preserved from ORACC metadata.",
    "collection": "Catalogue collection value preserved from ORACC metadata.",
    # Sections
    "synthetic": "1 when a section node was created explicitly to recover a malformed source state.",
    "chunk_type": "Source CDL chunk type preserved on generic structural chunk nodes.",
    "chunk_subtype": "Source CDL chunk subtype preserved when present.",
    "implicit": "Source implicit-section marker value preserved when present.",
    "face": "Source face/surface identifier used as the Text-Fabric face section feature.",
    "column_id": "Source column identifier preserved on column nodes.",
    "line": "Source line-start identifier used as the Text-Fabric line section feature.",
    "lnno": "OldBabylonian-compatible alias of the preserved source line label.",
    # Words / lexemes
    "frag": "Source fragment string preserved on the word occurrence when present.",
    "form": "Source written/transliterated word form.",
    "lang": "Source language code attached to a word or lexeme.",
    "cf": "ORACC citation form (lemma) attached to the analysis.",
    "gw": "ORACC guide word used to disambiguate the citation form.",
    "sense": "ORACC contextual sense attached to the word analysis when present.",
    "norm": "ORACC normalized word form when the source supplies one.",
    "pos": "ORACC lexical part-of-speech value.",
    "epos": "ORACC effective part-of-speech value for the occurrence when present.",
    "inst": "Source occurrence/compound analysis string preserved from ORACC.",
    "sig": "Full ORACC occurrence analysis signature; this is not a lexeme identifier.",
    "lemmaknown": "1 when the source word has a genuine lexical analysis; 0 for placeholders/unlemmatized words.",
    "gdl_json": "Canonical JSON serialization of the word's source GDL value, preserving absent/null/list distinctions.",
    "lexeme": "Canonical JSON key [lang, cf, gw, pos] identifying an ORACC-TF lexeme node.",
    # Semantic/structural edges
    "face_document": "Links a face node to its source-qualified document.",
    "column_face": "Links a column node to its containing face.",
    "line_face": "Links a line node to its containing face.",
    "line_column": "Links a line node to its containing column when the source has one.",
    "word_line": "Links a source word occurrence to its source line.",
    "word_lex": "Links a source word occurrence to one or more lexeme nodes parsed from its analysis.",
}


def description_for(name: str) -> str:
    """Return a non-empty feature description or fail closed."""
    description = FEATURE_DESCRIPTIONS.get(name, "").strip()
    if not description:
        raise KeyError(name)
    return description
