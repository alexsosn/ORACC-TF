"""RED acceptance contracts for a source-aware standalone TF browser smoke (#75)."""

from __future__ import annotations

from pathlib import Path
from importlib.util import module_from_spec, spec_from_file_location

from test_issue73_browser_usability import TF_VERSION, _generate


# pytest's pythonpath intentionally contains tests/ and programs/, not the
# repository root. Import the CLI directly by its canonical file path.
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "measure_issue75_browser.py"
_spec = spec_from_file_location("measure_issue75_browser", SCRIPT)
assert _spec is not None and _spec.loader is not None
_module = module_from_spec(_spec)
_spec.loader.exec_module(_module)
BrowserSmokeError = _module.BrowserSmokeError
smoke_browser = _module.smoke_browser
validate_browser_query = _module.validate_browser_query
validate_browser_passage = _module.validate_browser_passage
validate_expanded_word_features = _module.validate_expanded_word_features


def test_real_browser_smoke_uses_source_glyph_word_and_empty_anchors(tmp_path: Path) -> None:

    tf_root, app_root = _generate(tmp_path)
    result = smoke_browser(
        tf_root,
        app_root,
        version=TF_VERSION,
        document_key="fixture/project:Q000073",
        line_ref="Q000073.1",
        expected_glyph="𒀀",
        expected_form="a",
    )
    assert result["browser_routes"] == {
        "/": 200,
        "/passage": 200,
        "/query": 200,
        "/export": 200,
    }
    assert result["document_key"] == "fixture/project:Q000073"
    assert result["cuneiform_verified"] is True
    assert result["transliteration_verified"] is True
    assert result["synthetic_sign_count"] >= 1
    assert result["synthetic_signs_visible"] is False
    assert result["word_lex_edges"] >= 1
    assert result["search_has_result"] is True
    assert result["browser_query_results"] >= 1
    assert result["browser_passage_formats"] == {
        "text-orig-full": "𒀀",
        "text-trans-full": "a",
    }
    assert result["browser_passage_sections"][0] == "fixture/project:Q000073"
    assert result["browser_passage_sections"][-1] == "Q000073.1"
    assert result["browser_selected_section"] == "Q000073.1"
    assert result["browser_word_features"] == {"cf": "abu", "gw": "father"}
    assert result["browser_lexical_section"] == "Q000073.1"
    assert result["browser_help_link"].startswith("https://")
    assert result["browser_help_link"].endswith("#word_lex")


def test_browser_smoke_refuses_missing_or_ambiguous_document_key(tmp_path: Path) -> None:
    import pytest

    tf_root, app_root = _generate(tmp_path)
    for bad_key in ("Q000073", "other-project:Q000073"):
        with pytest.raises(BrowserSmokeError, match="document_key"):
            smoke_browser(
                tf_root,
                app_root,
                version=TF_VERSION,
                document_key=bad_key,
                line_ref="Q000073.1",
                expected_glyph="𒀀",
                expected_form="a",
            )


def test_browser_query_response_parser_rejects_missing_or_false_results() -> None:
    import pytest

    for invalid in (None, [], {}, {"status": True}, {"status": False, "nResults": 10}, {"status": True, "nResults": 0}):
        with pytest.raises(BrowserSmokeError, match="browser query"):
            validate_browser_query(invalid)
    assert validate_browser_query({"status": True, "nResults": 1}) == 1


def test_workflow_writes_structured_browser_evidence_without_stdout_redirect() -> None:
    workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/issue83-install-research.yml").read_text(encoding="utf-8")
    assert "--output /tmp/issue83-results/browser-semantic.json" in workflow
    assert "> /tmp/issue83-results/browser-semantic.json" not in workflow


def test_browser_passage_response_parser_ignores_navigation_only_text() -> None:
    import pytest

    assert validate_browser_passage(
        {"table": "<section><span>𒀀</span></section>", "passages": "other"},
        "𒀀",
    ) is True
    assert validate_browser_passage(
        {
            "table": '<details class="pretty focus" seq="Q000073.1"><summary>𒀀</summary></details>',
            "passages": "",
        },
        "𒀀",
        selected_section="Q000073.1",
    ) is True
    with pytest.raises(BrowserSmokeError, match="browser passage"):
        validate_browser_passage(
            {
                "table": '<details class="pretty" seq="Q000073.2"><summary>𒀀</summary></details>',
                "passages": "",
            },
            "𒀀",
            selected_section="Q000073.1",
        )
    for invalid in (
        None,
        [],
        {},
        {"table": "", "passages": "𒀀"},
        {"table": "<span>unrelated</span>", "passages": "𒀀"},
    ):
        with pytest.raises(BrowserSmokeError, match="browser passage"):
            validate_browser_passage(invalid, "𒀀")


def test_browser_workflow_checks_actual_versioned_release_archive() -> None:
    workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/issue83-install-research.yml").read_text(encoding="utf-8")
    selected_step = workflow.split(
        "- name: Source-aware browser query and text smoke without builder", 1
    )[1].split("- name: Cold-profile Python load", 1)[0]
    assert '"/tmp/issue83-release-clean"' in selected_step
    assert '"/tmp/issue83-clean/$DATASET"' not in selected_step


def test_expanded_passage_inspects_source_features_not_summary_or_other_line() -> None:
    import pytest

    selected = '''<details seq="Q000073.1" class="pretty focus" open>
      <summary>a</summary><div class="pretty"><span class="cf" title="cf">abu</span><span class="gw" title="gw">father</span></div>
    </details>'''
    assert validate_expanded_word_features(
        {"table": selected}, "Q000073.1", {"cf": "abu", "gw": "father"}
    )
    for invalid in (
        {"table": '<details seq="Q000073.1" class="pretty focus"><summary>abu father</summary></details>'},
        {"table": '<details seq="Q000073.1" class="pretty focus" open><summary>abu father</summary><div class="pretty"></div></details>'},
        {"table": '<details seq="Q000073.2" class="pretty focus" open><div class="pretty">abu father</div></details>'},
        {"table": '<details seq="Q000073.1" class="pretty focus" open><div class="pretty">abu</div></details>'},
        {"table": '<details seq="Q000073.1" class="pretty focus" open><div class="pretty"><span>abu</span><span>father</span></div></details>'},
        {"table": '<details seq="Q000073.1" class="pretty focus" open><div class="pretty"><span class="cf">father</span><span class="gw">abu</span></div></details>'},
        {"table": '<div>abu father</div>'},
        None,
    ):
        with pytest.raises(BrowserSmokeError, match="expanded browser"):
            validate_expanded_word_features(
                invalid, "Q000073.1", {"cf": "abu", "gw": "father"}
            )



def test_browser_workflow_follows_real_pinned_feature_help_link() -> None:
    workflow = (
        Path(__file__).resolve().parents[1] / ".github/workflows/issue83-install-research.yml"
    ).read_text(encoding="utf-8")
    browser_step = workflow.split(
        "- name: Source-aware browser query and text smoke without builder", 1
    )[1].split("- name: Cold-profile Python load", 1)[0]
    assert 'assert result["browser_help_link"] == expected_help' in browser_step
    assert 'https://raw.githubusercontent.com/$GITHUB_REPOSITORY/$GITHUB_SHA/docs/reference/features.md' in browser_step
    assert "grep -Fq '<a id=\\\"word_lex\\\"></a>'" in browser_step
