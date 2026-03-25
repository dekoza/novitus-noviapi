from __future__ import annotations

import contextlib

import pytest

from noviapi import NoviApiClient
from noviapi._hardware_polling import poll_hardware_request
from noviapi.exceptions import NoviApiError
from noviapi.models import NonFiscal, PrintLine, TextLine


@pytest.mark.hardware
@pytest.mark.hardware_stateful
def test_hardware_nf_printout_flow(hardware_base_url: str) -> None:
    printout = NonFiscal(
        lines=[
            PrintLine(
                textline=TextLine(
                    text='Greetings from the test suite!',
                    masked=False,
                )
            )
        ]
    )

    with NoviApiClient(hardware_base_url) as client:
        request_id: str | None = None
        try:
            created = client.nf_printout_send(printout)
            request_id = created.request.id
            assert created.request.status == 'STORED'

            confirmed = client.nf_printout_confirm(request_id)
            assert confirmed.request.id == request_id
            assert confirmed.request.status == 'CONFIRMED'

            checked = poll_hardware_request(
                client.nf_printout_check,
                request_id,
                timeout_ms=30_000,
            )
            assert checked.request.status == 'DONE'
            assert checked.request.error is None
            assert checked.device.status == 'OK'
        except Exception:
            if request_id is not None:
                with contextlib.suppress(NoviApiError):
                    client.nf_printout_cancel(request_id)
            raise
