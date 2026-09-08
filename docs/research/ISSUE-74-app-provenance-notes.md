# ISSUE-74 research notes

This file is working evidence for the source-independent portion of issue #74. It is not a replacement for the normative app plan.

## Pinned Text-Fabric behavior

Text-Fabric 13.1.0 at `dd227ce62b5536de53a0e20eac98c0459da8fd3d` restricts `provenanceSpec` to its documented keys. `webFeature` values are appended to `webBase`; `webUrl` otherwise derives links from section headings. Release-specific ORACC-TF fields therefore must not be inserted as unsupported YAML keys.

## Current authoritative release inputs

P-005 manifest schema 3 provides the semantic dataset id, generated repository, immutable release id, TF schema version, builder commit, optional source-state digest, provenance-complete flag, TF tree digest, immutable release ledger, and visible-root ownership. It does not provide an authoritative DOI or corpus-wide licence.

## Source-link evidence

The checked-in colliding editions carry distinct source project URLs:

- `data/rinap/rinap5/corpusjson/Q003840.json` -> `http://oracc.org/rinap/rinap5`
- `data/rinap/rinap5p1/corpusjson/Q003840.json` -> `http://oracc.org/rinap/rinap5p1`

A document link may therefore be constructed from source-provided project URL plus `textid`, after cross-checking the source project against the qualified subproject. Bare Q-number routing is forbidden.

Current ORACC indexing confirms subproject document routes such as `rinap/rinap5/Q003842/`, but direct availability is intermittent. The implementation preserves the source-provided ORACC base rather than rewriting it to another host.

No stable line-anchor or canonical external lexeme-id mapping was established. Both are omitted in the first contract rather than guessed.
