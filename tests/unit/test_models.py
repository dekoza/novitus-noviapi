from __future__ import annotations

import json
from decimal import Decimal

import pytest
from pydantic import ValidationError

from noviapi.models import (
    ApiExceptionDetails,
    Article,
    ArticleCode,
    Base64Payload,
    CheckResponse,
    ConfigurationCommand,
    ConfigurationOption,
    ConfigurationRange,
    Container,
    DeviceControl,
    DirectIOCommand,
    ErrorEnvelope,
    GraphicCommand,
    Item,
    LockCommand,
    NonFiscal,
    NonFiscalSystemInfo,
    NonFiscalSystemNumber,
    PrintLine,
    Receipt,
    StatusCommand,
    Summary,
    SystemInfo,
    SystemQRCode,
    TextLine,
)


def _minimal_article() -> Article:
    return Article(
        name='Coffee',
        ptu='A',
        quantity=Decimal('1'),
        price=Decimal('10.00'),
        value=Decimal('10.00'),
    )


def test_article_rejects_code_and_description_together() -> None:
    with pytest.raises(ValidationError):
        Article(
            name='Coffee',
            ptu='A',
            quantity=Decimal('1'),
            price=Decimal('10.00'),
            value=Decimal('10.00'),
            code=ArticleCode(print_as='barcode', value='123'),
            description='Ground coffee',
        )


def test_receipt_supports_container_variants() -> None:
    receipt = Receipt(
        items=[
            Item(container=Container(value=Decimal('2.50'), number=7)),
            Item(container_return=Container(value=Decimal('2.50'))),
        ],
        summary=Summary(total=Decimal('5.00'), pay_in=Decimal('5.00')),
    )

    payload = json.loads(
        receipt.model_dump_json(exclude_none=True, by_alias=True)
    )

    assert payload['items'][0]['container']['number'] == 7
    assert payload['items'][1]['container_return']['value'] == '2.50'


def test_direct_io_requires_exactly_one_packet_variant() -> None:
    DirectIOCommand(nov_cmd=Base64Payload(base64='AA=='))

    with pytest.raises(ValidationError):
        DirectIOCommand()

    with pytest.raises(ValidationError):
        DirectIOCommand(
            nov_cmd=Base64Payload(base64='AA=='),
            xml_cmd=Base64Payload(base64='AQ=='),
        )


def test_graphic_requires_operation_specific_fields() -> None:
    GraphicCommand(operation='program', id=1, base64='AA==')
    GraphicCommand(operation='reset', id=2)
    GraphicCommand(operation='read_indexes')

    with pytest.raises(ValidationError):
        GraphicCommand(operation='program', id=1)

    with pytest.raises(ValidationError):
        GraphicCommand(operation='reset')


def test_configuration_requires_operation_specific_fields() -> None:
    ConfigurationCommand(
        operation='program',
        options=[ConfigurationOption(key=1, value='x')],
    )
    ConfigurationCommand(operation='read_array', to_read=[1, 2])
    ConfigurationCommand(
        operation='read_range',
        range=ConfigurationRange(from_=10, to=20),
    )
    ConfigurationCommand(operation='read_all')

    with pytest.raises(ValidationError):
        ConfigurationCommand(operation='program')

    with pytest.raises(ValidationError):
        ConfigurationCommand(operation='read_array')

    with pytest.raises(ValidationError):
        ConfigurationCommand(operation='read_range')


def test_non_fiscal_system_number_is_text_only() -> None:
    NonFiscal(
        lines=[PrintLine(textline=TextLine(text='Hello', masked=False))],
        system_info=NonFiscalSystemInfo(
            system_number=NonFiscalSystemNumber(
                print_as='text', value='SYS-1'
            ),
        ),
    )

    with pytest.raises(ValidationError):
        NonFiscalSystemNumber(print_as='barcode', value='SYS-1')


def test_receipt_supports_qr_code_and_activity_monitor_flag() -> None:
    receipt = Receipt(
        items=[Item(article=_minimal_article())],
        summary=Summary(total=Decimal('10.00'), pay_in=Decimal('10.00')),
        system_info=SystemInfo(
            qr_code=SystemQRCode(qr_type=1, value='https://example.test/qr'),
        ),
        device_control=DeviceControl(send_to_activity_monitor=True),
    )

    payload = json.loads(
        receipt.model_dump_json(exclude_none=True, by_alias=True)
    )

    assert payload['system_info']['qr_code'] == {
        'qr_type': 1,
        'value': 'https://example.test/qr',
    }
    assert payload['device_control']['send_to_activity_monitor'] is True


def test_status_command_restricts_known_status_types() -> None:
    StatusCommand(type='fiscal_memory')

    with pytest.raises(ValidationError):
        StatusCommand(type='whatever')


def test_lock_command_requires_known_operation() -> None:
    LockCommand(operation='enable')

    with pytest.raises(ValidationError):
        LockCommand(operation='lock')


def test_check_response_parses_status_payload_variants() -> None:
    response = CheckResponse.model_validate(
        {
            'device': {'status': 'OK'},
            'request': {
                'status': 'DONE',
                'id': '1' * 32,
                'response': {
                    'status': {
                        'fiscal_memory': {
                            'unique_number': '1234567890123',
                            'tax_id': '1234567890',
                            'size': 1,
                            'max_daily_reports': 100,
                            'daily_reports_count': 2,
                            'last_daily_report_date': '2026-01-01 10:11:12',
                            'start_fiscal_date': '2025-01-01 10:11:12',
                        },
                        'device': {
                            'name': 'POINT',
                            'version': '1.00',
                            'characters_per_line': 42,
                            'tax_rates': [{'name': 'A', 'value': '23.00'}],
                            'totals': [
                                {
                                    'tax_rate': 'A',
                                    'receipt': '12.345678',
                                    'invoice': '0.000000',
                                }
                            ],
                        },
                    }
                },
            },
        }
    )

    assert response.request.response is not None
    assert response.request.response.status is not None
    assert response.request.response.status.fiscal_memory is not None
    assert response.request.response.status.fiscal_memory.unique_number == (
        '1234567890123'
    )
    assert response.request.response.status.device is not None
    assert response.request.response.status.device.tax_rates[0].name == 'A'


def test_error_envelope_preserves_validation_errors_and_refresh_date() -> None:
    envelope = ErrorEnvelope(
        exception=ApiExceptionDetails(
            code=429,
            description='Too many token requests',
            allowed_refresh_date='2026-03-25T12:00:00Z',
            errors=['receipt.items.0.article.value'],
        )
    )

    payload = json.loads(
        envelope.model_dump_json(exclude_none=True, by_alias=True)
    )

    assert (
        payload['exception']['allowed_refresh_date'] == '2026-03-25T12:00:00Z'
    )
    assert payload['exception']['errors'] == ['receipt.items.0.article.value']
