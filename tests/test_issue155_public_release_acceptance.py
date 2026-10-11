"""RED-first contract for fresh-runner acceptance of *public* v1.0.0 bytes.

The behavioral gate is the actual GitHub Actions job: this fixture only guards
its essential safety boundaries, not its successful execution.
"""
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / (
    ".github/workflows/issue155-public-release-smoke.yml"
)


def test_public_release_acceptance_is_independent_read_only_and_exact() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "pull_request:" in source
    assert "contents: read" in source
    assert "contents: write" not in source
    assert "actions/checkout@" not in source  # no ORACC-TF source tree or builder
    assert "pip install -e" not in source
    assert "gh release create" not in source
    assert "publish_1_0" not in source

    tag = "https://github.com/alexsosn/ORACC-TF/releases/download/v1.0.0"
    name = "assyrian-royal-inscriptions-1.0.0.zip"
    digest = "788f580604e30054fab34c4c3ea60ec3eb4f399412f1da90f778469d03507468"
    assert tag in source
    assert name in source
    assert name + ".sha256" in source
    assert digest in source
    assert "41285702" in source
    assert "sha256sum -c" in source
    assert "python -m zipfile -e" in source

    assert "text-fabric==13.1.0" in source
    assert 'importlib.util.find_spec("oracc_tf")' in source
    assert 'use(f"app:{root / \'app\'}"' in source
    assert "riao/ria1:Q001801" in source
    assert "Q001801.1" in source
    assert "text-orig-full" in source
    assert "text-trans-full" in source
    assert "translation_unit" in source
    assert "word_lex" in source
    assert "docs/reference/query-guide.md" in source
    assert "scripts/measure_issue75_browser.py" in source
    assert "raw.githubusercontent.com/alexsosn/ORACC-TF/v1.0.0" in source
    assert "--require-translation" in source
    assert "browser_translation_results" in source
