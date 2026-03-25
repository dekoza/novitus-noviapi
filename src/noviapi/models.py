from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

BASE64_PATTERN = (
    r'^(?:[A-Za-z0-9+/]{4})*'
    r'(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$'
)
REQUEST_DATE_PATTERN = (
    r'([0-9]{2})([:/\-.]{1})([0-9]{2})([:/\-.]{1})([0-9]{4})$'
)

Money = Annotated[Decimal, Field(ge=0, max_digits=11, decimal_places=2)]
Quantity = Annotated[Decimal, Field(ge=0, max_digits=15, decimal_places=6)]
Rate = Annotated[Decimal, Field(ge=0, max_digits=13, decimal_places=4)]
TotalAmount = Annotated[Decimal, Field(ge=0, max_digits=15, decimal_places=6)]
RequestId = Annotated[str, StringConstraints(min_length=32, max_length=32)]
Base64String = Annotated[
    str,
    StringConstraints(min_length=1, max_length=100000, pattern=BASE64_PATTERN),
]
RequestDate = Annotated[str, StringConstraints(pattern=REQUEST_DATE_PATTERN)]


def _exactly_one(model: BaseModel, field_names: tuple[str, ...]) -> None:
    count = sum(
        getattr(model, field_name) is not None for field_name in field_names
    )
    if count != 1:
        joined = ', '.join(field_names)
        raise ValueError(f'Exactly one of {joined} must be set')


def _at_most_one(model: BaseModel, field_names: tuple[str, ...]) -> None:
    count = sum(
        getattr(model, field_name) is not None for field_name in field_names
    )
    if count > 1:
        joined = ', '.join(field_names)
        raise ValueError(f'At most one of {joined} may be set')


class NoviBaseModel(BaseModel):
    model_config = ConfigDict(extra='forbid', populate_by_name=True)


class Discount(NoviBaseModel):
    type: Literal[
        'percent_discount',
        'percent_markup',
        'value_discount',
        'value_markup',
    ]
    name: (
        Annotated[str, StringConstraints(min_length=1, max_length=20)] | None
    ) = None
    value: Money


class ArticleCode(NoviBaseModel):
    print_as: Literal['text', 'barcode', 'qrcode']
    value: Annotated[str, StringConstraints(min_length=1, max_length=191)]


class Article(NoviBaseModel):
    name: Annotated[str, StringConstraints(min_length=1, max_length=60)]
    ptu: Annotated[str, StringConstraints(min_length=1, max_length=1)]
    quantity: Quantity
    price: Money
    value: Money
    unit: (
        Annotated[str, StringConstraints(min_length=1, max_length=4)] | None
    ) = None
    discount_markup: Discount | None = None
    code: ArticleCode | None = None
    description: (
        Annotated[
            str,
            StringConstraints(min_length=1, max_length=177),
        ]
        | None
    ) = None

    @model_validator(mode='after')
    def validate_code_and_description(self) -> Self:
        if self.code is not None and self.description is not None:
            raise ValueError('code and description are mutually exclusive')
        return self


class Advance(NoviBaseModel):
    description: Annotated[str, StringConstraints(min_length=1, max_length=60)]
    ptu: Annotated[str, StringConstraints(min_length=1, max_length=1)]
    value: Money


class Container(NoviBaseModel):
    name: (
        Annotated[str, StringConstraints(min_length=1, max_length=60)] | None
    ) = None
    number: Annotated[int, Field(ge=0, le=9999)] | None = None
    quantity: Money | None = None
    value: Money


class CashPayment(NoviBaseModel):
    value: Money


class NamedPayment(NoviBaseModel):
    name: (
        Annotated[str, StringConstraints(min_length=1, max_length=24)] | None
    ) = None
    value: Money


class CurrencyPayment(NoviBaseModel):
    course: Rate
    currency_value: Money
    local_value: Money
    is_change: bool
    name: Annotated[str, StringConstraints(min_length=3, max_length=3)]


class Summary(NoviBaseModel):
    discount_markup: Discount | None = None
    total: Money
    pay_in: Money
    change: Money | None = None


class EDocument(NoviBaseModel):
    transaction_id: Annotated[
        str, StringConstraints(min_length=1, max_length=100)
    ]
    protocol: Literal['NOVITUS', 'MF'] | None = None
    print_send_mode: (
        Literal[
            'print_no_send',
            'no_print_send_later',
            'print_send_later',
            'always_print_and_send_later',
        ]
        | None
    ) = None


class ReceiptBuyer(NoviBaseModel):
    nip: (
        Annotated[str, StringConstraints(min_length=1, max_length=16)] | None
    ) = None
    e_document: EDocument | None = None


class SystemNumber(NoviBaseModel):
    print_as: Literal['text', 'barcode', 'qrcode']
    value: Annotated[str, StringConstraints(min_length=1, max_length=512)]


class NonFiscalSystemNumber(NoviBaseModel):
    print_as: Literal['text']
    value: Annotated[str, StringConstraints(min_length=1, max_length=512)]


class SystemQRCode(NoviBaseModel):
    qr_type: Literal[0, 1]
    value: Annotated[str, StringConstraints(min_length=1, max_length=271)]


class DeviceControl(NoviBaseModel):
    open_drawer: bool | None = None
    feed_after_printout: bool | None = None
    paper_cut: Literal['none', 'full', 'part'] | None = None
    send_to_activity_monitor: bool | None = None


class DailyReportDeviceControl(NoviBaseModel):
    send_to_activity_monitor: bool | None = None


class SystemInfo(NoviBaseModel):
    cashier_name: (
        Annotated[str, StringConstraints(min_length=1, max_length=32)] | None
    ) = None
    cash_number: (
        Annotated[str, StringConstraints(min_length=1, max_length=8)] | None
    ) = None
    system_number: SystemNumber | None = None
    qr_code: SystemQRCode | None = None


class NonFiscalSystemInfo(NoviBaseModel):
    cashier_name: (
        Annotated[str, StringConstraints(min_length=1, max_length=32)] | None
    ) = None
    cash_number: (
        Annotated[str, StringConstraints(min_length=1, max_length=8)] | None
    ) = None
    system_number: NonFiscalSystemNumber | None = None


class DailyReportSystemInfo(NoviBaseModel):
    cashier_name: (
        Annotated[str, StringConstraints(min_length=1, max_length=32)] | None
    ) = None
    cash_number: (
        Annotated[str, StringConstraints(min_length=1, max_length=8)] | None
    ) = None


class Item(NoviBaseModel):
    article: Article | None = None
    advance: Advance | None = None
    advance_return: Advance | None = None
    container: Container | None = None
    container_return: Container | None = None

    @model_validator(mode='after')
    def validate_variant(self) -> Self:
        _exactly_one(
            self,
            (
                'article',
                'advance',
                'advance_return',
                'container',
                'container_return',
            ),
        )
        return self


class Payment(NoviBaseModel):
    cash: CashPayment | None = None
    card: NamedPayment | None = None
    cheque: NamedPayment | None = None
    coupon: NamedPayment | None = None
    other: NamedPayment | None = None
    credit: NamedPayment | None = None
    account: NamedPayment | None = None
    currency: CurrencyPayment | None = None
    transfer: NamedPayment | None = None
    mobile: NamedPayment | None = None
    voucher: NamedPayment | None = None

    @model_validator(mode='after')
    def validate_variant(self) -> Self:
        _exactly_one(
            self,
            (
                'cash',
                'card',
                'cheque',
                'coupon',
                'other',
                'credit',
                'account',
                'currency',
                'transfer',
                'mobile',
                'voucher',
            ),
        )
        return self


class TextLine(NoviBaseModel):
    bold: bool | None = None
    invers: bool | None = None
    center: bool | None = None
    right: bool | None = None
    font_number: Literal[0, 1, 2] | None = None
    big: bool | None = None
    height: Literal[2, 4] | None = None
    width: Literal[2, 4] | None = None
    text: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    masked: bool


class Barcode(NoviBaseModel):
    text: Annotated[str, StringConstraints(min_length=1, max_length=52)]
    masked: bool


class QRCode(NoviBaseModel):
    text: Annotated[str, StringConstraints(min_length=1, max_length=1852)]
    masked: bool


class SpecialLine(NoviBaseModel):
    type: Literal['emptyline', 'underline', 'last_receipt_number']


class NonFiscalGraphic(NoviBaseModel):
    number: Annotated[int, Field(ge=0, le=1023)]


class AsciiArtLine(NoviBaseModel):
    bold: bool | None = None
    invers: bool | None = None
    center: bool | None = None
    right: bool | None = None
    font_number: Literal[0, 1, 2] | None = None
    big: bool | None = None
    height: Literal[2, 4] | None = None
    width: Literal[2, 4] | None = None
    text: Annotated[str, StringConstraints(min_length=1, max_length=64)]


class PrintLine(NoviBaseModel):
    textline: TextLine | None = None
    barcode: Barcode | None = None
    qrcode: QRCode | None = None
    special_line: SpecialLine | None = None
    graphic: NonFiscalGraphic | None = None
    ascii_art: AsciiArtLine | None = None

    @model_validator(mode='after')
    def validate_variant(self) -> Self:
        _exactly_one(
            self,
            (
                'textline',
                'barcode',
                'qrcode',
                'special_line',
                'graphic',
                'ascii_art',
            ),
        )
        return self


class Receipt(NoviBaseModel):
    items: Annotated[list[Item], Field(min_length=1, max_length=255)]
    payments: (
        Annotated[list[Payment], Field(min_length=1, max_length=16)] | None
    ) = None
    summary: Summary
    printout_lines: (
        Annotated[
            list[PrintLine],
            Field(min_length=1, max_length=50),
        ]
        | None
    ) = None
    buyer: ReceiptBuyer | None = None
    system_info: SystemInfo | None = None
    device_control: DeviceControl | None = None


class NonFiscalOptions(NoviBaseModel):
    without_header: bool | None = None
    left_margin: bool | None = None
    copy_only: bool | None = None
    fiscal_margins_off: bool | None = None


class NonFiscal(NoviBaseModel):
    options: NonFiscalOptions | None = None
    lines: Annotated[list[PrintLine], Field(min_length=1, max_length=1000)]
    e_document: EDocument | None = None
    system_info: NonFiscalSystemInfo | None = None
    device_control: DeviceControl | None = None


class InvoiceInfo(NoviBaseModel):
    number: Annotated[str, StringConstraints(min_length=1, max_length=56)]
    copy_count: Annotated[int, Field(ge=0, le=10)] | None = None
    date_of_sell: RequestDate | None = None
    date_of_payment: RequestDate | None = None
    payment_form: (
        Annotated[str, StringConstraints(min_length=1, max_length=20)] | None
    ) = None
    paid: (
        Annotated[str, StringConstraints(min_length=1, max_length=29)] | None
    ) = None


class InvoiceBuyer(NoviBaseModel):
    name: Annotated[str, StringConstraints(min_length=1, max_length=256)]
    id_type: Literal['nip', 'regon', 'pesel'] | None = None
    id: Annotated[str, StringConstraints(min_length=1, max_length=16)]
    label_type: Literal['recipient', 'buyer'] | None = None
    address: Annotated[
        list[Annotated[str, StringConstraints(max_length=64)]],
        Field(min_length=1, max_length=8),
    ]
    e_document: EDocument | None = None


class InvoicePerson(NoviBaseModel):
    name: (
        Annotated[str, StringConstraints(min_length=1, max_length=60)] | None
    ) = None
    print_info: Literal[
        'place_for_signature',
        'name_and_place_for_signature',
        'none',
    ]


class InvoiceOptions(NoviBaseModel):
    skip_description_value_to_pay: bool | None = None
    skip_block_gross_value_in_accounting_tax: bool | None = None
    buyer_bold: bool | None = None
    seller_bold: bool | None = None
    buyer_nip_bold: bool | None = None
    seller_nip_bold: bool | None = None
    print_label_description_symbol_in_invoice_header: bool | None = None
    print_position_number_invoice: bool | None = None
    to_pay_label_before_acounting_tax_block: bool | None = None
    print_cents_in_words: bool | None = None
    dont_print_sell_date_if_equal_create_date: bool | None = None
    dont_print_seller_data_in_header: bool | None = None
    dont_print_sell_items_description: bool | None = None
    enable_payment_form: bool | None = None
    dont_print_customer_data: bool | None = None
    print_payd_in_cash: bool | None = None
    skip_seller_label: bool | None = None
    print_invoice_tax_label: bool | None = None


class AdditionalInfoLine(NoviBaseModel):
    text: Annotated[str, StringConstraints(max_length=64)]
    bold: bool | None = None
    justification: Literal['center', 'right', 'left'] | None = None


class Invoice(NoviBaseModel):
    info: InvoiceInfo
    buyer: InvoiceBuyer
    recipient: InvoicePerson | None = None
    seller: InvoicePerson | None = None
    options: InvoiceOptions | None = None
    items: Annotated[list[Item], Field(min_length=1, max_length=255)]
    payments: (
        Annotated[list[Payment], Field(min_length=1, max_length=16)] | None
    ) = None
    summary: Summary
    printout_lines: (
        Annotated[
            list[PrintLine],
            Field(min_length=1, max_length=50),
        ]
        | None
    ) = None
    additional_info: (
        Annotated[list[AdditionalInfoLine], Field(min_length=1)] | None
    ) = None
    system_info: SystemInfo | None = None
    device_control: DeviceControl | None = None


class DailyReport(NoviBaseModel):
    date: RequestDate
    system_info: DailyReportSystemInfo | None = None
    device_control: DailyReportDeviceControl | None = None


class Base64Payload(NoviBaseModel):
    base64: Base64String


class EFTCommand(NoviBaseModel):
    operation: Literal['transaction', 'communication_test']
    document_id: (
        Annotated[str, StringConstraints(min_length=1, max_length=20)] | None
    ) = None
    brutto: Money | None = None
    netto: Money | None = None
    vat: Money | None = None
    currency: (
        Annotated[str, StringConstraints(min_length=3, max_length=3)] | None
    ) = None
    cashback: Money | None = None
    max_cashback: Money | None = None
    additional_info: (
        Annotated[str, StringConstraints(min_length=1, max_length=100)] | None
    ) = None


class GraphicCommand(NoviBaseModel):
    id: Annotated[int, Field(ge=0, le=1023)] | None = None
    base64: Base64String | None = None
    operation: Literal['program', 'reset', 'get_crc', 'read_indexes']

    @model_validator(mode='after')
    def validate_required_fields(self) -> Self:
        if self.operation == 'program' and (
            self.id is None or self.base64 is None
        ):
            raise ValueError('program operation requires id and base64')
        if self.operation != 'read_indexes' and self.id is None:
            raise ValueError(f'{self.operation} operation requires id')
        return self


class ConfigurationRange(NoviBaseModel):
    from_: int = Field(alias='from')
    to: int


class ConfigurationOption(NoviBaseModel):
    key: int
    value: str


class ConfigurationCommand(NoviBaseModel):
    operation: Literal['program', 'read_array', 'read_range', 'read_all']
    options: (
        Annotated[list[ConfigurationOption], Field(min_length=1)] | None
    ) = None
    to_read: Annotated[list[int], Field(min_length=1)] | None = None
    range: ConfigurationRange | None = None

    @model_validator(mode='after')
    def validate_required_fields(self) -> Self:
        if self.operation == 'program' and self.options is None:
            raise ValueError('program operation requires options')
        if self.operation == 'read_array' and self.to_read is None:
            raise ValueError('read_array operation requires to_read')
        if self.operation == 'read_range' and self.range is None:
            raise ValueError('read_range operation requires range')
        return self


class StatusCommand(NoviBaseModel):
    type: Literal['fiscal_memory', 'device', 'protected_memory']


class DirectIOCommand(NoviBaseModel):
    xml_cmd: Base64Payload | None = None
    nov_cmd: Base64Payload | None = None

    @model_validator(mode='after')
    def validate_variant(self) -> Self:
        _exactly_one(self, ('xml_cmd', 'nov_cmd'))
        return self


class LockDisplay(NoviBaseModel):
    main_text: str | None = None
    info_text: str | None = None


class LockCommand(NoviBaseModel):
    operation: Literal['enable', 'disable']
    display: LockDisplay | None = None


class TokenResponse(NoviBaseModel):
    token: str
    expiration_date: datetime


class QueueStatusResponse(NoviBaseModel):
    requests_in_queue: int


class QueueDeleteResponse(NoviBaseModel):
    status: Literal['DELETED']


class ParseErrorDetails(NoviBaseModel):
    code: int
    description: str
    line: int


class ApiExceptionDetails(NoviBaseModel):
    allowed_refresh_date: datetime | None = None
    code: int | None = None
    description: str | None = None
    parse_error: ParseErrorDetails | None = None
    errors: list[str] | None = None


class ErrorEnvelope(NoviBaseModel):
    exception: ApiExceptionDetails
    daily_report_id: RequestId | None = None


class DeviceError(NoviBaseModel):
    code: int
    description: str


class DeviceStatus(NoviBaseModel):
    status: Literal['OK', 'ERROR']
    error: DeviceError | None = None

    @model_validator(mode='after')
    def validate_error_presence(self) -> Self:
        if self.status == 'ERROR' and self.error is None:
            raise ValueError('error is required when device status is ERROR')
        if self.status == 'OK' and self.error is not None:
            raise ValueError('error is not allowed when device status is OK')
        return self


class EDocumentStatus(NoviBaseModel):
    status: Literal[
        'printed_and_invalid_kid',
        'not_printed_and_sent',
        'not_printed_and_added_to_db',
        'printed_and_sent',
        'printed_and_added_to_db',
        'printed',
    ]
    code: int


class RequestError(NoviBaseModel):
    code: int
    description: str


class EFTTransactionResponse(NoviBaseModel):
    agent: str
    amount: Money
    card_token: str
    cashback: Money
    code: int
    eft_id: str
    error_code: int
    message: str
    transaction_id: str


class GraphicResponse(NoviBaseModel):
    image_id: Annotated[int, Field(ge=0, le=1023)] | None = None
    total_len: int | None = None
    hex_crc: str | None = None
    programmed_indexes: list[Annotated[int, Field(ge=0, le=1023)]] | None = (
        None
    )


class ConfigurationReadItem(NoviBaseModel):
    key: int
    value: str


class PacketResponse(NoviBaseModel):
    protocol: Literal['NOVITUS', 'XML']
    value: Base64String


class TaxRate(NoviBaseModel):
    name: Annotated[str, StringConstraints(min_length=1, max_length=1)]
    value: str


class TotalsItem(NoviBaseModel):
    tax_rate: Annotated[str, StringConstraints(min_length=1, max_length=1)]
    receipt: TotalAmount
    invoice: TotalAmount


class FiscalMemoryStatus(NoviBaseModel):
    unique_number: Annotated[
        str, StringConstraints(min_length=13, max_length=13)
    ]
    tax_id: str
    size: int
    max_daily_reports: int
    daily_reports_count: int
    last_daily_report_date: datetime
    start_fiscal_date: datetime


class ProtectedMemoryStatus(NoviBaseModel):
    number: int
    label: str
    last_jpkid: str
    size: int
    free: int


class DeviceDetails(NoviBaseModel):
    name: str
    version: str
    characters_per_line: int
    tax_rates: list[TaxRate]
    totals: list[TotalsItem]


class StatusReadResponse(NoviBaseModel):
    fiscal_memory: FiscalMemoryStatus | None = None
    protected_memory: ProtectedMemoryStatus | None = None
    device: DeviceDetails | None = None


class ResponsePayload(NoviBaseModel):
    status: StatusReadResponse | None = None
    eft: EFTTransactionResponse | None = None
    graphic: GraphicResponse | None = None
    configuration: list[ConfigurationReadItem] | None = None
    packet: PacketResponse | None = None

    @model_validator(mode='after')
    def validate_variant(self) -> Self:
        _at_most_one(
            self,
            ('status', 'eft', 'graphic', 'configuration', 'packet'),
        )
        return self


class RequestStatus(NoviBaseModel):
    status: Literal['STORED', 'QUEUED', 'PENDING', 'DONE', 'ERROR', 'UNKNOWN']
    id: RequestId | None = None
    e_document: EDocumentStatus | None = None
    jpkid: int | None = None
    response: ResponsePayload | None = None
    error: RequestError | None = None


class CreatedRequest(NoviBaseModel):
    status: Literal['STORED']
    id: RequestId


class ConfirmedRequest(NoviBaseModel):
    status: Literal['CONFIRMED']
    id: RequestId


class DeletedRequest(NoviBaseModel):
    status: Literal['DELETED']


class CreatedResponse(NoviBaseModel):
    request: CreatedRequest


class ConfirmedResponse(NoviBaseModel):
    request: ConfirmedRequest


class DeleteResponse(NoviBaseModel):
    request: DeletedRequest


class CheckResponse(NoviBaseModel):
    device: DeviceStatus
    request: RequestStatus
    exception: ApiExceptionDetails | None = None
