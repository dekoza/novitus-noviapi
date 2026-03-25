from __future__ import annotations

import pytest

from noviapi import NoviApiClient
from noviapi.models import StatusCommand


@pytest.mark.hardware
@pytest.mark.hardware_stateful
def test_hardware_status_device_flow(hardware_base_url: str) -> None:
    with NoviApiClient(hardware_base_url) as client:
        queue_before = client.queue_check()
        created = client.status_send(StatusCommand(type='device'))
        request_id = created.request.id

        confirmed = client.status_confirm(request_id)
        checked = client.status_check(request_id, timeout=30_000)
        queue_after = client.queue_check()

    assert queue_before.requests_in_queue >= 0
    assert confirmed.request.id == request_id
    assert checked.request.id == request_id
    assert checked.request.response is not None
    assert checked.request.response.status is not None
    assert checked.request.response.status.device is not None
    assert queue_after.requests_in_queue >= 0
