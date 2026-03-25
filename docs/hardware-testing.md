# Hardware testing

Hardware tests are development-only checks that run against a real Novitus
printer exposing NoviAPI over HTTP. They are intentionally opt-in because the
library cannot guarantee what a misconfigured device or environment will do.

Do not run hardware tests against a production printer.

## Requirements

- A real Novitus fiscal printer connected to a development workstation or lab
  network.
- NoviAPI service reachable over HTTP from the machine running pytest.
- A device base URL that is either the printer root (for example
  `http://192.168.1.50:8888`) or already ends with `/api/v1` (for example
  `http://192.168.1.50:8888/api/v1`).
- A development environment with project dependencies installed via `uv sync`.
- Confidence that no other workstation is actively driving the same printer.

## Required environment

Export the base URL before running any hardware tests:

```bash
export NOVIAPI_BASE_URL="http://192.168.1.50:8888/api/v1"
```

Root-style URLs are also accepted and normalized to `/api/v1` automatically.
A trailing slash after `/api/v1` is also accepted and removed internally.

Then enable the hardware test gate explicitly:

```bash
uv run pytest tests/hardware -m hardware --run-hardware
```

If `--run-hardware` is omitted, the suite skips all hardware tests.
If `NOVIAPI_BASE_URL` is missing, pytest fails immediately with a usage error.
If `PYTEST_XDIST_WORKER` is present, hardware tests abort because parallel
workers are unsafe for a shared real device.

## What the current hardware suite does

The current hardware suite is intentionally narrow:

- `comm_test()` checks basic reachability without authentication.
- `queue_check()` verifies authenticated access without mutating printer state.
- `status_send(StatusCommand(type='device'))` requests a read-only device status
  operation.
- `status_confirm()` confirms the queued status request.
- `status_check()` polls for the resulting device status payload. Its `timeout`
  argument uses milliseconds, so `timeout=30_000` means a 30-second poll.
- `nf_printout_send(NonFiscal(...))` submits a stateful non-fiscal printout with
  the text `Greetings from the test suite!`.
- `nf_printout_confirm()` confirms the queued non-fiscal printout.
- `nf_printout_check()` polls for the final non-fiscal printout status.

Stateful hardware tests retry `*_check(..., timeout=30_000)` up to three
attempts total when the printer returns `QUEUED` or `PENDING`, because a single
long-poll response is not guaranteed to reach a terminal state.

The status-flow test is treated as stateful because it enqueues and confirms a
live request even though the requested operation is intended to be read-only.
The non-fiscal printout test is also stateful because it prints a real message
on paper.

These tests are chosen because they should not print fiscal documents, clear the
queue, or modify device configuration. The non-fiscal printout test still
consumes paper, so run it only when that output is acceptable.

## Recommended procedure

Before starting:

- Make sure the target printer is a dedicated development device.
- Make sure the device is idle and not serving another workstation.
- Make sure the configured `NOVIAPI_BASE_URL` points to the intended printer.
- Do not use `pytest-xdist`; hardware tests refuse `PYTEST_XDIST_WORKER`.
- Avoid running the hardware suite in parallel from multiple shells.

Run the default hardware suite:

```bash
uv run pytest tests/hardware -m hardware --run-hardware
```

Stateful tests stay skipped unless you pass `--run-hardware-stateful`.

Run the stateful status-flow test only when you explicitly want to allow queued
live-device work:

```bash
uv run pytest tests/hardware/test_status_flow.py -m hardware_stateful \
  --run-hardware --run-hardware-stateful -x
```

Run the non-fiscal printout test only when you explicitly want the printer to
print `Greetings from the test suite!`:

```bash
uv run pytest tests/hardware/test_nf_printout.py -m hardware_stateful \
  --run-hardware --run-hardware-stateful -x
```

Run a single test when diagnosing printer behavior:

```bash
uv run pytest tests/hardware/test_queue_status.py -m hardware --run-hardware -x
```

## Interpreting failures

- `comm_test()` failure usually means the printer or NoviAPI service is not
  reachable at the configured URL, or the device rejects the API root probe.
- Authentication failures on `queue_check()` or the status flow usually mean
  the device rejected token acquisition or another workstation invalidated the
  token.
- `status_check()` timeouts usually mean the device did not finish the request
  within the polling window or the printer is blocked by another activity. A
  value like `timeout=30_000` asks the device to poll for up to 30 seconds.
- A `QUEUED` or `PENDING` status after one check does not necessarily mean
  failure; the hardware tests retry long-poll checks up to three attempts total
  before giving up.
- `nf_printout_check()` failures usually mean the printer rejected or did not
  finish the non-fiscal printout request.
- A skip on the status-flow test usually means you forgot
  `--run-hardware-stateful`.

## Safety boundaries

- Receipt, invoice, daily report, lock, and configuration programming hardware
  tests remain out of bounds unless they are separately justified and documented
  as safe on a real printer.
- Do not point `NOVIAPI_BASE_URL` at a production device.
- Do not assume a staging network is safe just because it is not public.
