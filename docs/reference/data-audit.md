---
title: Source-to-TF audit and known source gaps
status: active
---

# Source-to-TF audit and known source gaps

The `assyrian-royal-inscriptions` release has a direct source-to-Text-Fabric audit. It compares one explicit source revision with an already-built TF candidate and reports source membership, qualified document and word identities, semantic-sign identities and payloads, line and lexeme identities, word-to-line and word-to-lexeme relations, catalogue joins, round-trip accounting, and synthetic-anchor payload checks.

Run it against a locally built candidate with:

```bash
python scripts/audit_source_to_tf.py \
  --data data \
  --tf-dir /path/to/tf-candidate \
  --source-revision <git-revision> \
  --dataset assyrian-royal-inscriptions
```

For the release candidate, the `issue124-source-to-tf-audit` workflow builds TF from the same checkout, publishes the canonical JSON report as an artifact, and rejects any non-empty `unexplained` list. The JSON report is the authoritative place for current counts and exact affected identities. The workflow also verifies that the in-scope source tree still matches the pinned revision. `source.members_manifest` and `source.catalogue_manifest` record stable relative paths and SHA-256 hashes, while `source.source_state_sha256` fingerprints those manifests as one source state.

## Known source limitations

A passing audit does not mean that every upstream source member supplies the same kinds of information. The report keeps these source states explicit instead of silently filling them in:

- **Unreadable corpusjson members.** Zero-byte or otherwise unreadable source members appear under `source.hazards`. They do not become TF document nodes, and the loader does not invent an identity from a filename.
- **Readable editions without catalogue records.** These editions remain in TF. Their exact qualified keys appear under `catalogue.missing_document_keys`; consumers should treat absent catalogue metadata as absent rather than inferred.
- **Catalogue-only records.** Catalogue entries with no readable in-scope corpusjson edition appear under `catalogue.unmatched_catalogue_keys`. They are metadata records, not textual documents, and therefore do not become TF document nodes.
- **Form round-trip exceptions.** `roundtrip.exceptions` records source-grounded classes such as structural context, fragment/continuation context, editorial markup, unreadable signs and zero-sign words. A passing audit requires every source word to be accounted for; it does not claim that every normalized word form is mechanically reconstructible from a flat sign sequence.
- **Synthetic empty slots.** Zero-span textual entities use explicit `synthetic=1` slots as described in [ADR-0001](architecture/ADR-0001-empty-slots-not-sidecars.md). The audit excludes those technical anchors from semantic-sign reconciliation and fails if source sign payload leaks onto them.

## Reading the result

Use `reconciliation` for source-versus-TF identity and cardinality checks, `semantic_content_mismatches` for same-cardinality payload or relation drift, `source.hazards` and `catalogue` for explicit upstream gaps, and `unexplained` for discrepancies that are neither expected source states nor accepted modelling behavior.

This audit is source-grounded. It does not compare against a previous ORACC-TF release and does not certify publication or upstream-update workflows.
