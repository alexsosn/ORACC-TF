"""Issue #72/#16 contract for the emitted TF schema identity."""

from oracc_tf import TF_VERSION


def test_display_and_translation_features_advance_tf_schema_version() -> None:
    assert TF_VERSION == "0.4.0"
