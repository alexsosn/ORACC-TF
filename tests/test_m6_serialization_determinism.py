from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import tf.core.data as tf_data

from oracc_tf import corpus, loader, metadata


def _edition() -> loader.Edition:
    text_id = "QDETERMINISM"
    doc = {
        "type": "cdl",
        "textid": text_id,
        "cdl": [
            {
                "node": "c",
                "type": "text",
                "id": f"{text_id}.U0",
                "cdl": [
                    {"node": "d", "type": "surface", "ref": "", "label": ""},
                    {
                        "node": "d",
                        "type": "line-start",
                        "ref": f"{text_id}.1",
                        "label": "1",
                    },
                    {
                        "node": "l",
                        "id": f"{text_id}.l1",
                        "f": {
                            "form": "a",
                            "gdl": [{"v": "a", "utf8": "𒀀"}],
                        },
                    },
                ],
            }
        ],
    }
    return loader.Edition(
        subproject="test/unit",
        text_id=text_id,
        path=Path(f"/test/unit/corpusjson/{text_id}.json"),
        doc=doc,
        word_count=1,
    )


def _tf_bytes(root: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in sorted(root.glob("*.tf"))}


def test_tf_serialization_is_byte_deterministic_across_writer_timestamps(
    tmp_path: Path, monkeypatch
) -> None:
    edition = _edition()
    left = tmp_path / "left"
    right = tmp_path / "right"

    monkeypatch.setattr(
        tf_data,
        "utcnow",
        lambda: datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )
    corpus.build_tf(
        left,
        editions=(edition,),
        metadata_index=metadata.MetadataIndex.empty(),
    )

    monkeypatch.setattr(
        tf_data,
        "utcnow",
        lambda: datetime(2026, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
    )
    corpus.build_tf(
        right,
        editions=(edition,),
        metadata_index=metadata.MetadataIndex.empty(),
    )

    left_files = _tf_bytes(left)
    right_files = _tf_bytes(right)
    assert left_files
    assert left_files == right_files

    assert corpus.load_tf(left).F.otype.maxSlot == 1
    assert corpus.load_tf(right).F.otype.maxSlot == 1
