# P-002 Phase 1 research note — upstream configuration and lock contract

Date: 2026-09-05

## Inputs rechecked

This phase is constrained by R-002 §§2–6 and P-002 Phase 1. ORACC exposes rolling ZIP archives under `/json/`, but publishes no immutable version id or checksum. The repository's extracted snapshot no longer retains the source ZIPs, so provenance cannot be reconstructed from Git history alone.

The active dataset mapping from Phase 0 contains exactly eleven RIAO/RINAP archives. `etcsri` is intentionally not an active daily input; it remains a later real-change integration fixture.

## Contract decisions

1. `upstream.toml` is hand-edited policy and contains only source endpoints and updater policy. The tracked archive set remains derived from `datasets.toml`, avoiding two independently editable inventories.
2. `upstream.lock.json` is generated data. Serialization must be canonical UTF-8 JSON with sorted archive keys, deterministic field order, two-space indentation, and exactly one trailing newline. Volatile fetch time is excluded from the byte-stable lock contract; HTTP validators describe the recorded archive response, not when our client happened to fetch it.
3. Every lock archive record must contain the source URL, SHA-256, byte length, ETag, Last-Modified, ORACC `UTC-timestamp`, licence string, extraction paths, and `text_ids_sha256`. Optional HTTP validators may be null because servers/proxies can omit them; content identity fields may not be absent.
4. `text_ids_sha256` is a deterministic digest over sorted text id/content-SHA pairs, not merely the set of ids. This permits cheap detection of renamed/moved versus changed texts on later updates.
5. Lock generation is fail-closed: unknown archive names, malformed SHA-256 values, negative sizes, invalid timestamps, duplicate extraction paths/text ids, or records for archives outside the active dataset mapping are rejected.
6. Backfill is non-destructive. Fresh upstream ZIPs are compared with the committed extraction and produce an explicit report; Phase 1 must never overwrite `data/` as a side effect of provenance backfill.

## Gate decomposition

The phase is implemented in three gates:

- **PH1-A:** configuration parser + deterministic lock model/serialization, entirely fixture-testable.
- **PH1-B:** live backfill of all eleven active archives and generation of the initial lock plus extraction-difference report.
- **PH1-C:** clean-checkout regeneration test proving the recorded archives reproduce the committed lock bytes and that any extraction drift is explicitly reported.

Network-dependent PH1-B/C must use the canonical `/json/<archive>.zip` endpoint and validate ZIP structure; HTTP 200 alone is not evidence of a valid archive. If live ORACC access or licence evidence cannot be evaluated, finalization stops rather than fabricating lock values.
