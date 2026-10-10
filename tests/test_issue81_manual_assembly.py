"""RED contracts for lightweight standalone researcher-manual assembly (#81)."""

from __future__ import annotations

from pathlib import Path

import pytest

from oracc_tf import manual


def _source(tmp_path: Path) -> Path:
    root = tmp_path / "builder"
    reference = root / "docs" / "reference"
    (reference / "features" / "word").mkdir(parents=True)
    for filename in manual.REQUIRED_REFERENCE_PAGES:
        (reference / filename).write_text(f"# {filename}\n", encoding="utf-8")
    (reference / "features" / "word" / "form.md").write_text(
        "# form\n", encoding="utf-8"
    )
    (reference / "model.svg").write_text("<svg/>", encoding="utf-8")
    (root / "docs" / "research").mkdir(parents=True)
    (root / "docs" / "research" / "secret.md").write_text("never stage", encoding="utf-8")
    (root / "docs" / "plans").mkdir(parents=True)
    (root / "docs" / "plans" / "dev.md").write_text("never stage", encoding="utf-8")
    (root / "docs" / "task-state").mkdir(parents=True)
    (root / "docs" / "task-state" / "state.json").write_text("{}\n", encoding="utf-8")
    (root / "CITATION.cff").write_text("cff-version: 1.2.0\n", encoding="utf-8")
    (root / "LICENSE_SCOPE.md").write_text("# Licence scope\n", encoding="utf-8")
    return root


def test_manual_assembler_copies_only_user_facing_material(tmp_path: Path) -> None:
    root = _source(tmp_path)
    stage = tmp_path / "standalone-docs"
    manual.assemble_manual(root, stage, dataset="assyrian-royal-inscriptions")
    assert (stage / "index.md").is_file()
    assert "(reference/index.md)" in (stage / "index.md").read_text()
    assert (stage / "reference" / "quick-start.md").is_file()
    for name in ("scope.md", "text-formats.md", "browser.md", "references.md", "acknowledgements.md"):
        assert (stage / "reference" / name).is_file()
    assert (stage / "reference" / "features" / "word" / "form.md").is_file()
    assert (stage / "reference" / "model.svg").is_file()
    assert (stage / "CITATION.cff").is_file()
    assert (stage / "LICENSE_SCOPE.md").is_file()
    assert not any((stage / name).exists() for name in ("research", "plans", "task-state"))
    assert not any(p.name == "secret.md" for p in stage.rglob("*"))


def test_manual_assembler_rejects_missing_required_reference(tmp_path: Path) -> None:
    root = _source(tmp_path)
    (root / "docs" / "reference" / "query-guide.md").unlink()
    with pytest.raises(manual.ManualAssemblyError, match="query-guide.md"):
        manual.assemble_manual(root, tmp_path / "standalone-docs", dataset="dataset")


def test_manual_assembler_rejects_missing_citation_and_preserves_previous_stage(
    tmp_path: Path,
) -> None:
    root = _source(tmp_path)
    stage = tmp_path / "standalone-docs"
    manual.assemble_manual(root, stage, dataset="dataset")
    (root / "CITATION.cff").unlink()
    with pytest.raises(manual.ManualAssemblyError, match="CITATION.cff"):
        manual.assemble_manual(root, stage, dataset="dataset")
    assert (stage / "CITATION.cff").is_file()


def test_manual_assembler_replaces_old_tree_without_stale_content(tmp_path: Path) -> None:
    root = _source(tmp_path)
    stage = tmp_path / "standalone-docs"
    manual.assemble_manual(root, stage, dataset="dataset")
    (stage / "obsolete.md").write_text("should disappear", encoding="utf-8")
    (root / "docs" / "reference" / "features" / "word" / "form.md").unlink()
    manual.assemble_manual(root, stage, dataset="dataset")
    assert not (stage / "obsolete.md").exists()
    assert not (stage / "reference" / "features" / "word" / "form.md").exists()


def test_manual_assembler_rejects_symlink_and_source_overlap(tmp_path: Path) -> None:
    root = _source(tmp_path)
    (root / "docs" / "reference" / "evil.md").symlink_to(
        root / "docs" / "research" / "secret.md"
    )
    with pytest.raises(manual.ManualAssemblyError, match="symlink"):
        manual.assemble_manual(root, tmp_path / "docs-out", dataset="dataset")
    (root / "docs" / "reference" / "evil.md").unlink()
    with pytest.raises(manual.ManualAssemblyError, match="overlap"):
        manual.assemble_manual(root, root / "docs" / "reference" / "nested", dataset="dataset")


def test_manual_assembler_rejects_symlinked_docs_ancestor(tmp_path: Path) -> None:
    root = _source(tmp_path)
    external = tmp_path / "external-documents"
    (root / "docs").rename(external)
    (root / "docs").symlink_to(external, target_is_directory=True)
    with pytest.raises(manual.ManualAssemblyError, match="symlink"):
        manual.assemble_manual(root, tmp_path / "standalone-docs", dataset="dataset")


def test_manual_assembler_refuses_required_skeleton_instead_of_shipping_it(
    tmp_path: Path,
) -> None:
    root = _source(tmp_path)
    (root / "docs" / "reference" / "quick-start.md").write_text(
        "---\nstatus: skeleton\n---\n\nComing soon.\n",
        encoding="utf-8",
    )
    with pytest.raises(manual.ManualAssemblyError, match="quick-start.md.*skeleton"):
        manual.assemble_manual(root, tmp_path / "manual", dataset="dataset")


def test_manual_assembler_rejects_dangling_internal_links(tmp_path: Path) -> None:
    root = _source(tmp_path)
    original = root / "docs" / "reference" / "quick-start.md"
    original.write_text(
        "# Quick start\n\n[Broken guide](missing-guide.md#example)\n",
        encoding="utf-8",
    )
    with pytest.raises(manual.ManualAssemblyError, match="missing-guide.md"):
        manual.assemble_manual(root, tmp_path / "manual", dataset="dataset")


def test_manual_assembler_accepts_relative_links_and_fragments(tmp_path: Path) -> None:
    root = _source(tmp_path)
    ref = root / "docs" / "reference"
    (ref / "quick-start.md").write_text(
        "# Quick start\n\n[Features](features.md#feature-reference)\n"
        "[Model](model.md)\n[External](https://example.org/docs)\n",
        encoding="utf-8",
    )
    manual.assemble_manual(root, tmp_path / "manual", dataset="dataset")
    assert (tmp_path / "manual" / "reference" / "features.md").is_file()


def test_manual_assembler_rejects_maintainer_local_file_urls(tmp_path: Path) -> None:
    root = _source(tmp_path)
    (root / "docs" / "reference" / "quick-start.md").write_text(
        "# Guide\n\n[Private cache](file:///home/maintainer/private/cache)\n",
        encoding="utf-8",
    )
    with pytest.raises(manual.ManualAssemblyError, match="file://"):
        manual.assemble_manual(root, tmp_path / "manual", dataset="dataset")
