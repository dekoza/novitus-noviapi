from __future__ import annotations

import pytest

from noviapi import NoviApiClient


@pytest.mark.hardware
def test_hardware_queue_check(hardware_base_url: str) -> None:
    with NoviApiClient(hardware_base_url) as client:
        queue_status = client.queue_check()

    assert queue_status.requests_in_queue >= 0
