# Text-Fabric empty-slot precedents

This note records the external implementations behind ADR-0001 so future research agents do not repeat the same investigation.

## ETCBC/DSS

The DSS converter uses empty slots for otherwise-unanchored textual structures. Its documentation states that a `vac` cluster contains no signs and that an empty slot is generated to anchor it in the text sequence; the same is done for other clusters with no slots. The converter also creates an empty slot for a word with no glyphs (`type=empty`).

Relevant upstream files:

- `ETCBC/dss/docs/feature_documentation.md`
- `ETCBC/dss/programs/tfFromAbegg.py`

## Nino-cunei Old Babylonian / Old Assyrian

The shared `Nino-cunei/tfFromAtf/programs/convert.py` converter explicitly creates slots for otherwise-empty textual containers:

- an empty document gets `cv.slot()` when it would otherwise be unlinked;
- an empty line gets `cv.slot()`;
- comment-only lines use a slot carrying `type=commentline`.

Old Babylonian identifies `sign` as the TF slot type, so these anchors are ordinary TF slots in a cuneiform corpus without claiming that a real cuneiform sign exists at that position.

Relevant upstream repositories:

- `Nino-cunei/tfFromAtf`
- `Nino-cunei/oldbabylonian`

## Interpretation

The reusable pattern is not "fabricate a sign". It is "preserve a textual position with an explicitly non-semantic slot and label that slot so consumers can exclude it from philological sign counts".
