# NINMED — Nineveh Medical Encyclopaedia in Text-Fabric

**Corpus:** the ORACC `asbp/ninmed` edition of the *Nineveh Medical Encyclopaedia*, a project directed by Jon Taylor in collaboration with Mark Geller, funded by the Wellcome Trust. **Primary JSON snapshot timestamp:** `2024-07-05T13:32:14`.

The native ORACC-TF graph converts **159 readable source JSON bodies** into **65,089 actual source words**, preserving source line, word and GDL sign data, `cf` (citation form), `gw` (gloss) and `pos` (part of speech) with lexical `word_lex` relations where attested. A 160th source member, `P395407.json`, is zero bytes. It is quarantined as an explicit source exception, **not** represented as an empty medical text. The broader ORACC catalogue contains records without readable JSON bodies; those are not silently promoted to text editions.

This graph is an ORACC-based conversion and **does not reproduce** `Nino-cunei/ninmed`, which is a distinct ATF-derived edition. Among 34 matched source IDs, a pinned independent study found 33 differing complete word-form sequences. No alignment by word position or imported `uniqueLemma` is valid.

**Current availability:** the native converter can be installed locally, but a separately downloadable NINMED TF ZIP has **not yet been publicly released**. An ordinary point-and-click reader and search front end remain a product requirement, distinct from the existing expert TF browser.

Start with [Quick start](quick-start.md), [Source-specific features](features.md), and [Rights, acknowledgement and scope](rights.md). No official running translations are available in the converted JSON-derived graph.

