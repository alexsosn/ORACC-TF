"""Real-corpus M8 cross-validation against archived oldbabylonian TF 1.0.6.

The ordinary unit suite remains network-independent.  CI supplies
``OLDBABYLONIAN_TF`` from an immutable sparse checkout of
Nino-cunei/oldbabylonian@cd8ffe826a598af4715fd724387d9834ec1300d8.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from tf.fabric import Fabric


PINNED_COMMIT = "cd8ffe826a598af4715fd724387d9834ec1300d8"


def _oldbab_api():
    location = os.environ.get("OLDBABYLONIAN_TF")
    if not location:
        pytest.skip("real oldbabylonian TF is supplied by the dedicated M8 CI gate")
    path = Path(location)
    assert path.name == "1.0.6"
    assert (path / "readingu.tf").is_file()
    assert (path / "lnno.tf").is_file()
    tf = Fabric(locations=str(path), silent="deep")
    good = tf.loadAll(silent="deep")
    assert good and tf.api is not None
    return tf.api


def _populated_values(api, feature: str, otype: str) -> list[str]:
    f = api.Fs(feature)
    assert f is not None
    nodes = api.F.otype.s(otype)
    values = [f.v(node) for node in nodes]
    populated = [value for value in values if value is not None]
    assert populated, f"{feature} has no values on {otype} nodes"
    assert all(isinstance(value, str) for value in populated)
    return populated


def test_real_oldbabylonian_shared_features_have_the_pinned_domains():
    api = _oldbab_api()

    for feature in ("readingu", "lnno", "period", "genre"):
        assert api.Fs(feature).meta["valueType"] == "str"

    readingu = _populated_values(api, "readingu", "sign")
    lnno = _populated_values(api, "lnno", "line")
    period = _populated_values(api, "period", "document")
    genre = _populated_values(api, "genre", "document")

    # Domain witnesses come from the real pinned corpus, not copied fixtures.
    assert any(any(ord(char) > 0xFFFF for char in value) for value in readingu)
    assert any(value == "1" for value in lnno)
    assert any("Old Babylonian" in value for value in period)
    assert any(value == "Letter" for value in genre)
