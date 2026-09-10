from __future__ import annotations

import gc
from pathlib import Path
import weakref

from oracc_tf import loader


class _Payload(dict):
    """Weak-referenceable stand-in for a parsed corpusjson object."""


def test_duplicate_tracking_does_not_retain_previously_yielded_parsed_docs(
    monkeypatch,
) -> None:
    paths = (
        Path("/virtual/data/riao/ria1/corpusjson/Q000001.json"),
        Path("/virtual/data/riao/ria1/corpusjson/Q000002.json"),
    )
    payload_refs: list[weakref.ReferenceType[_Payload]] = []

    monkeypatch.setattr(loader, "source_files", lambda _data, _subprojects: list(paths))

    def fake_observe_source(path: Path, *, data: Path | None = None) -> loader.ReadableSource:
        del data
        payload = _Payload()
        payload_refs.append(weakref.ref(payload))
        edition = loader.Edition(
            subproject="riao/ria1",
            text_id=path.stem,
            path=path,
            doc=payload,
            word_count=0,
        )
        return loader.ReadableSource(
            edition=edition,
            relative_path=f"riao/ria1/corpusjson/{path.name}",
            bytes=1,
            sha256="0" * 64,
        )

    monkeypatch.setattr(loader, "observe_source", fake_observe_source)

    observations = loader.iter_source_observations(
        Path("/virtual/data"), subprojects=["riao/ria1"]
    )
    first = next(observations)
    assert payload_refs[0]() is not None

    del first
    second = next(observations)
    gc.collect()

    assert payload_refs[0]() is None

    del second
    observations.close()
