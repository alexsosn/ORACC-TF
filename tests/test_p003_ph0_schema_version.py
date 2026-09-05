"""P-003 Phase 0 — self-describing emitted metadata changes dataset schema."""

from oracc_tf import TF_VERSION


def test_feature_descriptions_advance_tf_schema_version():
    assert TF_VERSION == "0.3.0"
