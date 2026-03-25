from __future__ import annotations

import os

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        '--run-hardware',
        action='store_true',
        default=False,
        help='run tests that require a real Novitus fiscal printer',
    )
    parser.addoption(
        '--run-hardware-stateful',
        action='store_true',
        default=False,
        help='run hardware tests that enqueue or confirm live printer work',
    )


def pytest_runtest_setup(item: pytest.Item) -> None:
    if 'hardware_stateful' in item.keywords and not item.config.getoption(
        '--run-hardware-stateful'
    ):
        pytest.skip(
            'stateful hardware tests are disabled; '
            'pass --run-hardware-stateful to enable'
        )


@pytest.fixture
def hardware_base_url(request: pytest.FixtureRequest) -> str:
    if not request.config.getoption('--run-hardware'):
        pytest.skip(
            'hardware tests are disabled; pass --run-hardware to enable'
        )

    base_url = os.environ.get('NOVIAPI_BASE_URL')
    if not base_url:
        raise pytest.UsageError(
            'NOVIAPI_BASE_URL must be set when running --run-hardware tests'
        )

    if os.environ.get('PYTEST_XDIST_WORKER'):
        raise pytest.UsageError(
            'hardware tests refuse parallel workers; run without xdist'
        )

    return base_url
