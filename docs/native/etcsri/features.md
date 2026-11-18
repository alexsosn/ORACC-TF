# ETCSRI — graph and feature guide

<a id="form"></a>
<a id="base"></a>
<a id="morph"></a>
<a id="morph2"></a>
<a id="para_json"></a>
<a id="source_id"></a>
<a id="document_key"></a>
<a id="source_sha256"></a>
<a id="word_json"></a>
<a id="f_json"></a>
<a id="marker_json"></a>
<a id="sign_json"></a>

## Source morphology, not an inferred parser

Each `word` node retains ORACC's independent `form`, `base`, `morph`, `morph2` fields where present. The actual source word `Q000935.l04855` has `morph = N1=Urnammak` and `morph2 = N1=NAME`. They are **source strings**. This converter neither decomposes them into individual morpheme edges nor infers missing analyses; a mismatch or absence must remain visible.

`word_json`, `f_json`, `morphology_json`, `para_json` and `props_json` preserve the source-bearing payloads. In particular `para_json` comes from the original word-level `para` field rather than from a guessed TF paragraph boundary. The source snapshot includes 28,180 paired `morph`/`morph2` words and 3,584 `para`-annotated words, out of 29,573 total. Absence of a tag is not evidence of an absent source word.

## Reading and gaps

Nodes include `document`, `text`, `discourse`, `sentence`, `phrase`, `line`, `word`, `sign`, and `determinative`. `sign` slots preserve actual ORACC GDL semantics and `src_path` rather than treating every nested GDL wrapper as a new physical sign. Nontext `nonx` markers become `nontext_span`, and nonword `nonw` become `nonword_marker`. Their `marker_json` retains the original marker object. Synthetic anchors are explicitly `synthetic=1`; they are not recoverable Sumerian text or additional source signs.

Source IDs and `document_key` should be used for citation and joins. For `Q000935` the qualified key is `etcsri:Q000935`. Text-Fabric node numbers are build-specific and must not be cited as ORACC identities.

## Boundaries

The generated graph has no official running translation layer extracted from `index-tra.json`, which is an index over translation stems rather than readable line translations. Do not interpret `morph2` as an English translation. Full source-form/word/sign and event fidelity is checked against the pinned 1,456 JSON files in the repository's corpus acceptance tests.

