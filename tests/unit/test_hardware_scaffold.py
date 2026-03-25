from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HARDWARE_TEST_PATH = PROJECT_ROOT / 'tests' / 'hardware' / 'test_comm_test.py'
QUEUE_TEST_PATH = PROJECT_ROOT / 'tests' / 'hardware' / 'test_queue_status.py'
STATUS_TEST_PATH = PROJECT_ROOT / 'tests' / 'hardware' / 'test_status_flow.py'
PYPROJECT_PATH = PROJECT_ROOT / 'pyproject.toml'


def test_hardware_smoke_test_exists_and_is_marked() -> None:
    hardware_test = HARDWARE_TEST_PATH.read_text(encoding='utf-8')

    assert '@pytest.mark.hardware' in hardware_test
    assert 'def test_hardware_comm_test' in hardware_test
    assert 'client.comm_test() is True' in hardware_test


def test_hardware_queue_status_test_exists_and_is_marked() -> None:
    hardware_test = QUEUE_TEST_PATH.read_text(encoding='utf-8')

    assert '@pytest.mark.hardware' in hardware_test
    assert 'def test_hardware_queue_check' in hardware_test
    assert 'client.queue_check()' in hardware_test


def test_hardware_status_flow_test_exists_and_is_marked() -> None:
    hardware_test = STATUS_TEST_PATH.read_text(encoding='utf-8')

    assert '@pytest.mark.hardware' in hardware_test
    assert '@pytest.mark.hardware_stateful' in hardware_test
    assert 'def test_hardware_status_device_flow' in hardware_test
    assert "StatusCommand(type='device')" in hardware_test
    assert 'client.status_send' in hardware_test
    assert 'client.status_confirm' in hardware_test
    assert 'client.status_check' in hardware_test
    assert 'queue_before = client.queue_check()' in hardware_test
    assert 'queue_after = client.queue_check()' in hardware_test


def test_pyproject_registers_stateful_hardware_marker() -> None:
    pyproject = PYPROJECT_PATH.read_text(encoding='utf-8')

    assert (
        'hardware_stateful: enqueues or confirms live printer work'
        in pyproject
    )


def test_hardware_tests_are_skipped_without_opt_in() -> None:
    result = subprocess.run(
        [
            sys.executable,
            '-m',
            'pytest',
            'tests/hardware/test_comm_test.py',
            '-q',
        ],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
        env=os.environ | {'NOVIAPI_BASE_URL': 'http://127.0.0.1:8888/api/v1/'},
    )

    assert result.returncode == 0
    assert '1 skipped' in result.stdout


def test_hardware_tests_fail_fast_without_base_url() -> None:
    result = subprocess.run(
        [
            sys.executable,
            '-m',
            'pytest',
            'tests/hardware/test_comm_test.py',
            '-q',
            '--run-hardware',
        ],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
        env={
            key: value
            for key, value in os.environ.items()
            if key != 'NOVIAPI_BASE_URL'
        },
    )

    assert result.returncode != 0
    combined_output = result.stdout + result.stderr
    assert 'NOVIAPI_BASE_URL' in combined_output


def test_hardware_tests_refuse_parallel_worker_execution() -> None:
    result = subprocess.run(
        [
            sys.executable,
            '-m',
            'pytest',
            'tests/hardware/test_comm_test.py',
            '-q',
            '--run-hardware',
        ],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
        env=os.environ
        | {
            'NOVIAPI_BASE_URL': 'http://127.0.0.1:8888/api/v1/',
            'PYTEST_XDIST_WORKER': 'gw0',
        },
    )

    assert result.returncode != 0
    combined_output = result.stdout + result.stderr
    assert 'hardware tests refuse parallel workers' in combined_output


def test_stateful_hardware_tests_are_skipped_without_stateful_flag() -> None:
    result = subprocess.run(
        [
            sys.executable,
            '-m',
            'pytest',
            'tests/hardware/test_status_flow.py',
            '-q',
            '--run-hardware',
        ],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
        env=os.environ | {'NOVIAPI_BASE_URL': 'http://127.0.0.1:8888/api/v1/'},
    )

    assert result.returncode == 0
    assert '1 skipped' in result.stdout
