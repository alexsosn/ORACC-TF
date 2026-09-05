"""P-003 Phase 0 — documentation tree and generator/drift contracts."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tf.fabric import Fabric


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


def _tiny_tf(path: Path, *, token: str = "a") -> None:
    path.mkdir(parents=True, exist_ok=True)
    tf = Fabric(locations=str(path), silent="deep")
    assert tf.save(
        nodeFeatures={"otype": {1: "sign"}, "token": {1: token}},
        edgeFeatures={"oslots": {}},
        metaData={
            "": {"name": "docs-test", "version": "0.0.0"},
            "otype": {"valueType": "str", "description": "Node type."},
            "oslots": {"valueType": "str", "description": "Slot membership."},
            "token": {"valueType": "str", "description": "Fixture token."},
        },
        silent="deep",
    )


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


def test_generator_emits_feature_pages_and_full_drift_check_covers_tree(tmp_path):
    tf_dir = tmp_path / "tf"
    output = tmp_path / "reference" / "features.md"
    _tiny_tf(tf_dir)

    subprocess.run(
        [sys.executable, "scripts/gen_docs.py", "--tf", str(tf_dir), "--output", str(output)],
        check=True,
    )
    token_page = output.parent / "features" / "sign" / "token.md"
    assert token_page.is_file()
    assert "Fixture token." in token_page.read_text(encoding="utf-8")
    assert "Populated entries: 1" in token_page.read_text(encoding="utf-8")

    clean = subprocess.run(
        [sys.executable, "scripts/check_docs.py", "--tf", str(tf_dir), "--generated", str(output)],
        capture_output=True,
        text=True,
    )
    assert clean.returncode == 0, clean.stdout + clean.stderr

    token_page.unlink()
    missing = subprocess.run(
        [sys.executable, "scripts/check_docs.py", "--tf", str(tf_dir), "--generated", str(output)],
        capture_output=True,
        text=True,
    )
    assert missing.returncode != 0
    assert "drift" in (missing.stdout + missing.stderr).lower()

    subprocess.run(
        [sys.executable, "scripts/gen_docs.py", "--tf", str(tf_dir), "--output", str(output)],
        check=True,
    )
    token_tf = tf_dir / "token.tf"
    token_tf.write_text(
        token_tf.read_text(encoding="utf-8").replace("\n1\ta\n", "\n1\tb\n"),
        encoding="utf-8",
    )
    changed = subprocess.run(
        [sys.executable, "scripts/check_docs.py", "--tf", str(tf_dir), "--generated", str(output)],
        capture_output=True,
        text=True,
    )
    assert changed.returncode != 0
    assert "drift" in (changed.stdout + changed.stderr).lower()
