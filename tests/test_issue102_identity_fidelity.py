from __future__ import annotations

import json
from pathlib import Path

from oracc_tf import loader


def test_embedded_textid_is_not_silently_normalized(tmp_path: Path) -> None:
    data = tmp_path / "data"
    root = data / "riao" / "ria1" / "corpusjson"
    root.mkdir(parents=True)
    path = root / "Q000123.json"
    path.write_text(
        json.dumps({"type": "cdl", "textid": " Q000123 ", "cdl": []}),
        encoding="utf-8",
    )

    observation = loader.observe_source(path, data=data)

    assert isinstance(observation, loader.ReadableSource)
    assert observation.edition.text_id == " Q000123 "
    assert observation.edition.key == "riao/ria1: Q000123 "
