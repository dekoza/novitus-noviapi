from __future__ import annotations

import pytest

from noviapi import NoviApiClient


@pytest.mark.hardware
def test_hardware_comm_test(hardware_base_url: str) -> None:
    with NoviApiClient(hardware_base_url) as client:
        assert client.comm_test() is True
