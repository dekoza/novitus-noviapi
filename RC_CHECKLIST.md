# Release Candidate Checklist

A commit is not an RC until every item below is green for the exact revision
being released.

## Candidate

- [ ] Candidate commit SHA recorded
- [ ] Candidate version recorded (recommended first target: `0.2.0rc1`)
- [ ] Working tree is clean: `git status --short`
- [ ] Candidate was not created with suppressed hooks

## Gate 0: Local Hygiene

- [ ] `uv sync --frozen --all-groups`
- [ ] `uv run pre-commit run --all-files`
- [ ] `git diff --exit-code`
- [ ] `uv run ty check src tests scripts`

A candidate fails immediately if `pre-commit` rewrites files or if any hook was
bypassed and fixed later by hand.

## Automated Validation

- [ ] GitHub Actions CI is green for all required jobs
- [ ] `uv run pytest tests/contract tests/unit tests/integration --ignore=tests/unit/test_artifacts.py -x`
- [ ] `uv build --no-sources --clear`
- [ ] `uv run pytest tests/unit/test_artifacts.py -x`

## Artifact Rehearsal

### Wheel

- [ ] `uv venv build/rc-smoke-wheel --clear --no-project`
- [ ] `uv pip install --python build/rc-smoke-wheel dist/*.whl`
- [ ] `build/rc-smoke-wheel/bin/python -m noviapi._release_smoke`

### Source distribution

- [ ] `uv venv build/rc-smoke-sdist --clear --no-project`
- [ ] `uv pip install --python build/rc-smoke-sdist dist/*.tar.gz`
- [ ] `build/rc-smoke-sdist/bin/python -m noviapi._release_smoke`

## Hardware Evidence

Record evidence against the manufacturer-declared minimum supported versions
listed in `docs/hardware-testing.md`, and note separately that this library has
been personally verified only on `POINT` firmware `1.00` so far.

- [ ] `uv run pytest tests/hardware --run-hardware -m hardware` passes 3 times
- [ ] `uv run pytest tests/hardware/test_status_flow.py --run-hardware --run-hardware-stateful -m hardware_stateful -x` passes 3 times
- [ ] `uv run pytest tests/hardware/test_nf_printout.py --run-hardware --run-hardware-stateful -m hardware_stateful -x` passes 3 times

| Model | Firmware | Default suite x3 | Status flow x3 | NF printout x3 | Notes |
| --- | --- | --- | --- | --- | --- |
| | | | | | |

## Packaging And Metadata

- [ ] `pyproject.toml` no longer declares Alpha
- [ ] `README.md` no longer claims release blockers are still planned
- [ ] Supported Python versions match CI and package metadata
- [ ] Supported printer and firmware scope is documented

## Release Decision

- [ ] No known P0 or P1 release blockers remain
- [ ] Public API is frozen for the RC cycle
- [ ] Release notes list supported hardware and known limitations
- [ ] Tag planned as `v0.2.0rc1`

## Sign-off

- [ ] Engineering sign-off
- [ ] Hardware sign-off
- [ ] Packaging and release sign-off
