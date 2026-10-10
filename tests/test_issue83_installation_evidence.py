"""Researcher installation metrics must be attributed to the correct artifact (#83)."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "docs/reference/installation.md"


def test_installation_guide_does_not_conflate_measurement_zip_and_release_zip() -> None:
    guide = GUIDE.read_text(encoding="utf-8")
    assert "measurement-only ZIP" in guide
    assert "versioned release-format ZIP" in guide
    assert "different archives" in guide


def test_installation_guide_cites_current_actual_ci_evidence() -> None:
    guide = GUIDE.read_text(encoding="utf-8")
    assert "38070730938" in guide
    assert "41,294,294" in guide
    assert "1,837,544" in guide
    assert "1,830,660" in guide
    assert "27.279" in guide
    assert "28.829" in guide
