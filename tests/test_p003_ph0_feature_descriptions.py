"""P-003 Phase 0 — feature metadata must be self-describing."""

from __future__ import annotations

from pathlib import Path

import pytest

from oracc_tf import corpus


_RESERVED_WITHOUT_USER_DESCRIPTION = {"otext.tf"}


def _header(path: Path) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("@"):
            break
        key, _, value = line[1:].partition("=")
        metadata[key] = value
    return metadata


@pytest.mark.corpus
def test_every_emitted_tf_feature_has_nonempty_description(tmp_path):
    """The built dataset, not a handwritten feature list, defines coverage."""
    corpus.build_full_tf(tmp_path)

    feature_files = sorted(
        path
        for path in tmp_path.glob("*.tf")
        if path.name not in _RESERVED_WITHOUT_USER_DESCRIPTION
    )
    assert feature_files

    missing = []
    for path in feature_files:
        description = _header(path).get("description", "").strip()
        if not description:
            missing.append(path.stem)

    assert missing == [], f"TF features without @description: {missing}"
