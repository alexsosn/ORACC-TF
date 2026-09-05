"""P-003 Phase 0 — documentation tree and generator/drift contracts."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REFERENCE_PAGES = {
    "index.md",
    "model.md",
    "signs.md",
    "words-and-lexemes.md",
    "translations.md",
    "identity.md",
    "query-guide.md",
    "reproducibility.md",
    "features.md",
}


def test_reference_skeleton_is_complete_and_indexed():
    reference = Path("docs/reference")
    assert reference.is_dir()
    assert REFERENCE_PAGES <= {path.name for path in reference.glob("*.md")}

    docs_index = Path("docs/README.md").read_text(encoding="utf-8")
    for page in sorted(REFERENCE_PAGES):
        assert f"reference/{page}" in docs_index


def test_reference_pages_are_owned_by_reference_drift_not_maintainer_registry():
    """Generated per-feature pages must not require registry.json entries."""
    result = subprocess.run(
        [sys.executable, "scripts/check_docs_registry.py"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_generator_is_idempotent_and_preserves_manual_regions(tmp_path):
    output = tmp_path / "features.md"
    output.write_text(
        "generated-old\n"
        "<!-- manual:begin interpretation -->\n"
        "Keep this researcher-written explanation.\n"
        "<!-- manual:end -->\n",
        encoding="utf-8",
    )

    command = [
        sys.executable,
        "scripts/gen_docs.py",
        "--tf",
        str(tmp_path / "tf"),
        "--output",
        str(output),
        "--allow-empty-dataset",
    ]
    first = subprocess.run(command, check=True, capture_output=True, text=True)
    first_bytes = output.read_bytes()
    second = subprocess.run(command, check=True, capture_output=True, text=True)

    assert first.returncode == second.returncode == 0
    assert output.read_bytes() == first_bytes
    assert b"Keep this researcher-written explanation." in first_bytes


def test_drift_check_rejects_removed_manual_region(tmp_path):
    generated = tmp_path / "features.md"
    generated.write_text(
        "<!-- manual:begin interpretation -->\n"
        "Preserved text.\n"
        "<!-- manual:end -->\n",
        encoding="utf-8",
    )
    baseline = tmp_path / "baseline.md"
    baseline.write_bytes(generated.read_bytes())
    generated.write_text("generated only\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/check_docs.py",
            "--generated",
            str(generated),
            "--baseline",
            str(baseline),
            "--manual-regions-only",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "manual" in (result.stdout + result.stderr).lower()
