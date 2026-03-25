from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = PROJECT_ROOT / '.github' / 'workflows' / 'ci.yml'


def test_ci_workflow_runs_quality_checks_and_build() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding='utf-8')

    assert 'on:' in workflow
    assert 'pull_request:' in workflow
    assert 'push:' in workflow
    assert 'ubuntu-latest' in workflow
    assert "python-version: ['3.11', '3.12', '3.13']" in workflow
    assert 'astral-sh/setup-uv' in workflow
    assert 'uv sync --frozen --all-groups' in workflow
    assert 'uv run pre-commit run --all-files' in workflow
    assert (
        'uv run pytest tests/contract tests/unit tests/integration -x'
        in workflow
    )
    assert 'uv build --no-sources' in workflow
    assert 'uv run pytest tests/unit/test_artifacts.py -x' in workflow
