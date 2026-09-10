from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
PINNED_OLDBAB = "cd8ffe826a598af4715fd724387d9834ec1300d8"
PINNED_ISSUE102_SOURCE = "dd6a657d15999288948a266c9eb17666f9790497"


def _workflow(name: str) -> dict:
    with (WORKFLOWS / name).open(encoding="utf-8") as handle:
        value = yaml.load(handle, Loader=yaml.BaseLoader)
    assert isinstance(value, dict)
    return value


def _checkout_steps(job: dict) -> list[dict]:
    return [
        step
        for step in job.get("steps", [])
        if isinstance(step, dict) and step.get("uses") == "actions/checkout@v4"
    ]


def _run_commands(job: dict) -> tuple[str, ...]:
    return tuple(
        step["run"]
        for step in job.get("steps", [])
        if isinstance(step, dict) and isinstance(step.get("run"), str)
    )


def _sparse_paths(checkout: dict) -> str:
    with_values = checkout.get("with") or {}
    assert isinstance(with_values, dict)
    sparse = with_values.get("sparse-checkout")
    assert isinstance(sparse, str) and sparse.strip(), "checkout must declare sparse-checkout"
    return sparse


def test_pr_tests_split_fast_sparse_from_full_corpus_gate() -> None:
    workflow = _workflow("tests.yml")
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    assert "fast" in jobs, "fast/unit tests need a separate sparse-checkout job"
    assert "corpus" in jobs, "whole-corpus tests must remain a separate required job"

    fast = jobs["fast"]
    corpus = jobs["corpus"]
    fast_checkout = _checkout_steps(fast)[0]
    sparse = _sparse_paths(fast_checkout)
    assert "programs" in sparse
    assert "tests" in sparse
    assert "data" not in {line.strip() for line in sparse.splitlines()}
    assert any('pytest -q -m "not corpus"' in command for command in _run_commands(fast))

    corpus_checkout = _checkout_steps(corpus)[0]
    corpus_with = corpus_checkout.get("with") or {}
    corpus_sparse = corpus_with.get("sparse-checkout") if isinstance(corpus_with, dict) else None
    assert corpus_sparse is None or "data" in corpus_sparse
    assert any("pytest -q -m corpus" in command for command in _run_commands(corpus))

    trigger = workflow.get("on") or {}
    if isinstance(trigger, dict):
        pull_request = trigger.get("pull_request") or {}
        assert not isinstance(pull_request, dict) or "paths" not in pull_request


def test_docs_registry_uses_sparse_checkout_without_changing_validator() -> None:
    workflow = _workflow("tests.yml")
    job = workflow["jobs"]["docs-registry"]
    checkout = _checkout_steps(job)[0]
    sparse = _sparse_paths(checkout)
    assert "scripts" in sparse
    assert "docs" in sparse
    assert any("python scripts/check_docs_registry.py" in command for command in _run_commands(job))


def test_m8_primary_checkout_is_sparse_but_external_pin_is_unchanged() -> None:
    workflow = _workflow("m8-oldbabylonian.yml")
    job = workflow["jobs"]["cross-validate"]
    checkouts = _checkout_steps(job)
    assert len(checkouts) == 2

    primary, external = checkouts
    sparse = _sparse_paths(primary)
    assert "pyproject.toml" in sparse
    assert "programs" in sparse
    assert "tests/test_m8_oldbabylonian_integration.py" in sparse or "tests" in sparse

    external_with = external.get("with") or {}
    assert external_with["repository"] == "Nino-cunei/oldbabylonian"
    assert external_with["ref"] == PINNED_OLDBAB
    assert external_with["path"] == ".external/oldbabylonian"
    assert "tf/1.0.6" in external_with["sparse-checkout"]
    assert any(
        "pytest -q tests/test_m8_oldbabylonian_integration.py" in command
        for command in _run_commands(job)
    )


def test_issue102_harness_checkout_sparse_but_pinned_source_data_stays_exact() -> None:
    workflow = _workflow("issue102-unreadable-research.yml")
    job = workflow["jobs"]["census"]
    checkouts = _checkout_steps(job)
    assert len(checkouts) == 2

    harness, source = checkouts
    harness_sparse = _sparse_paths(harness)
    assert "scripts/research_issue102_unreadable.py" in harness_sparse or "scripts" in harness_sparse

    source_with = source.get("with") or {}
    assert source_with["repository"] == "alexsosn/ORACC-TF"
    assert source_with["ref"] == PINNED_ISSUE102_SOURCE
    assert source_with["path"] == ".external/source"
    assert "data" in source_with["sparse-checkout"]
    assert source_with["persist-credentials"] == "false"


def test_p003_keeps_full_checkout_and_real_corpus_build() -> None:
    workflow = _workflow("p003-docs.yml")
    job = workflow["jobs"]["generated-reference"]
    checkout = _checkout_steps(job)[0]
    with_values = checkout.get("with") or {}
    assert not isinstance(with_values, dict) or "sparse-checkout" not in with_values
    assert any(
        "corpus.build_full_tf('/tmp/oracc-tf')" in command
        for command in _run_commands(job)
    )
