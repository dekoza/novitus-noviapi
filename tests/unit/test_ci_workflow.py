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
    assert 'uv run ty check src tests scripts' in workflow
    assert 'uv run pytest tests/contract tests/unit tests/integration' in workflow
    assert '--ignore=tests/unit/test_artifacts.py -x' in workflow
    assert 'uv build --no-sources --clear' in workflow
    assert 'uv run pytest tests/unit/test_artifacts.py -x' in workflow
    assert 'scripts/release_smoke_test.py' not in workflow
    assert 'uv venv build/rc-smoke-wheel --clear --no-project' in workflow
    assert 'uv pip install --python build/rc-smoke-wheel dist/*.whl' in workflow
    assert 'build/rc-smoke-wheel/bin/python -m noviapi._release_smoke' in workflow
    assert 'uv venv build/rc-smoke-sdist --clear --no-project' in workflow
    assert 'uv pip install --python build/rc-smoke-sdist dist/*.tar.gz' in workflow
    assert 'build/rc-smoke-sdist/bin/python -m noviapi._release_smoke' in workflow
    assert workflow.index('uv build --no-sources --clear') < workflow.index(
        'uv run pytest tests/unit/test_artifacts.py -x'
    )
    assert workflow.index(
        'uv run pytest tests/unit/test_artifacts.py -x'
    ) < workflow.index('build/rc-smoke-wheel/bin/python -m noviapi._release_smoke')
    assert workflow.index(
        'build/rc-smoke-wheel/bin/python -m noviapi._release_smoke'
    ) < workflow.index('build/rc-smoke-sdist/bin/python -m noviapi._release_smoke')
