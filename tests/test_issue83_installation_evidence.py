"""The researcher guide distinguishes instrumented and publishable ZIPs (#83)."""

from pathlib import Path


GUIDE = Path(__file__).resolve().parents[1] / "docs/reference/installation.md"


def test_installation_guide_does_not_conflate_measurement_zip_and_release_zip() -> None:
    guide = GUIDE.read_text(encoding="utf-8")
    assert "measurement-only ZIP" in guide
    assert "versioned release-format ZIP" in guide
    assert "different archives" in guide
    assert "published asset" in guide


def test_installation_guide_identifies_real_measurement_and_its_limits() -> None:
    guide = GUIDE.read_text(encoding="utf-8")
    assert "https://github.com/alexsosn/ORACC-TF/actions/runs/" in guide
    assert "GitHub Actions Ubuntu" in guide
    assert "three times" in guide
    assert "not minimum hardware requirements" in guide
