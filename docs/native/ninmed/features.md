# NINMED — native lexical, structural and source features

NINMED's ORACC JSON uses `asbp/ninmed` and keys such as `asbp/ninmed:P285136`. Its `word` nodes represent actual source `node=l` words with attested `form`, `cf`, `gw`, `pos` and optional `sense`/`lang`, not reconstructed tokens from another edition. `word_lex` is a typed Text-Fabric edge linking source words to lexical entries.

For the real word `P285136.l003f2`, source `form = DU₃.DU₃.BI`, `cf = DÙ.DÙ.BI`, `gw = ritual (instructions)`, `pos = N`. The fact that a gloss is labelled `gw` does not give an English running translation of the line. Nino-cunei `uniqueLemma` is an independently defined field and is deliberately not imported as an ORACC citation form.

`word_json` preserves each complete original ORACC source word and `document_meta_json` keeps the edition header. `source_markers_json` preserves each source `node=d` structural, line-start, nontext and nonword event in traversal order, with a path of integer child indices through the original `cdl` tree. It is a **lossless document-level record**, not a claim that each source event has a separately addressable TF marker node. Do not infer line gaps or missing signs by expanding `extent`.

Text-Fabric graph nodes include `document`, line/section nodes, `word`, `sign` and `lex` where attested. Synthetic technical sign slots, when necessary to preserve structural TF locality, are marked `synthetic=1` and must not count as source GDL signs. Each word remains traceable through `document_key`, `source_id` and `source_sha256`.

No official running translation series is present in the native JSON-derived TF output. The built-in TF browser uses specialized TFQL query syntax; an ordinary text-search interface is still under development.

