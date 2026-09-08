"""Independent PH4 review regressions for established GDL container syntax."""

from __future__ import annotations

import pytest

from oracc_tf.source_diff import SourceDiffError, SourceDocument, snapshot_archive


def _snapshot(gdl: object):
    return snapshot_archive(
        dataset="fixture-dataset",
        archive="fixture-archive",
        source_state="sha256:" + "a" * 64,
        oracc_utc_timestamp="2026-08-07T12:00:00",
        licence="CC0",
        documents=[
            SourceDocument(
                subproject="p/a",
                document={
                    "type": "cdl",
                    "textid": "Q000001",
                    "cdl": [
                        {
                            "node": "l",
                            "id": "w1",
                            "f": {"form": "a", "gdl": gdl},
                        }
                    ],
                },
            )
        ],
    )


@pytest.mark.parametrize(
    "gdl",
    [
        [{"group": {"v": "a"}}],
        [{"seq": "not-a-list"}],
        [{"qualified": ["not-an-object"]}],
        [{"mods": [1]}],
    ],
)
def test_known_gdl_child_containers_remain_lists_of_objects(gdl: object) -> None:
    """Future-key recursion must not weaken syntax already frozen by P-001."""
    with pytest.raises(SourceDiffError):
        _snapshot(gdl)
