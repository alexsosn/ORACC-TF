"""Issue #69 contract for the BHSA documentation-breadth research conclusion."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "docs" / "research" / "R-006-tf-application-browser.md"


def test_r006_classifies_bhsa_documentation_breadth_for_oracc_tf() -> None:
    payload = RESEARCH.read_text(encoding="utf-8").lower()

    assert "## documentation breadth" in payload
    # The issue-69 scope amendment requires a product-level docs classification,
    # not only Text-Fabric's feature-help URL mechanics.
    for required in (
        "landing",
        "topic",
        "bibliograph",
        "history",
        "colophon",
        "news",
        "assets",
        "app-to-doc",
        "#78",
    ):
        assert required in payload

    # R-006 must distinguish reusable documentation patterns/categories from
    # BHSA-specific corpus content rather than cargo-culting reference pages.
    assert "adopt" in payload
    assert "not transferable" in payload
