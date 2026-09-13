"""Issue #72 RED contract for the emitted TF schema identity."""

from oracc_tf import TF_VERSION


def test_display_feature_advances_tf_schema_version() -> None:
    assert TF_VERSION == "0.3.0"
