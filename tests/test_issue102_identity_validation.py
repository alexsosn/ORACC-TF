from __future__ import annotations

import json
from pathlib import Path

from oracc_tf import loader


def test_surrounding_whitespace_does_not_get_normalized_into_a_source_identity(tmp_path: Path) -> None:
    data = tmp_path / "data"
    root = data / "riao" / "ria1" / "corpusjson"
    root.mkdir(parents=True)
    path = root / "Q000123.json"
    path.write_text(
        json.dumps({"type": "cdl", "textid": " Q000123 ", "cdl": []}),
        encoding="utf-8",
    )

    observation = loader.observe_source(path, data=data)

    assert isinstance(observation, loader.SourceHazard)
    assert observation.kind == "invalid-source-id"
    assert observation.source_id is None
