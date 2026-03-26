# CI/CD learning: build artifact tests must not run before the build step

## Incident

- Observed in GitHub Actions run `23567134437`, job `68621299113`.
- The workflow failed in `Run test suite` before reaching `Build artifacts`.
- `tests/unit/test_artifacts.py` crashed with `StopIteration` while looking for
  `dist/*.whl`.

## Exact bug

The CI workflow executed an artifact-inspection test inside the general unit test
phase:

```text
uv run pytest tests/contract tests/unit tests/integration -x
```

but only built the distributions afterwards:

```text
uv build --no-sources
uv run pytest tests/unit/test_artifacts.py -x
```

That ordering is invalid. `tests/unit/test_artifacts.py` depends on files in
`dist/`, so it is a build-phase test, not a normal unit test.

## Why it was easy to miss locally

Local development had stale artifacts in `dist/` from earlier builds. That hid
the workflow bug because the artifact test could accidentally find an old wheel
or sdist even when the current CI step had not built anything yet.

There was a second bug on top of the ordering bug:

- the test used `next(DIST_DIR.glob('*.whl'))`
- the test used `next(DIST_DIR.glob('*.tar.gz'))`

This makes artifact selection nondeterministic when `dist/` contains multiple
versions, and it fails with an unhelpful `StopIteration` when the expected build
output is missing.

## Fix applied

1. The main pytest step now excludes `tests/unit/test_artifacts.py`.
2. Artifact verification remains a dedicated step after `uv build`.
3. The build step now uses `uv build --no-sources --clear` so stale files do not
   leak into validation.
4. Artifact tests now select the current package version explicitly using
   `noviapi.__version__`.
5. Artifact tests now fail with a clear assertion when the expected current
   wheel or sdist is missing or duplicated.

## Prevention rules for agents

### Rule 1: classify tests by lifecycle dependency

If a test reads build outputs such as `dist/*.whl`, `dist/*.tar.gz`, generated
OpenAPI bundles, or packaged artifacts, it is not a plain unit test. It must run
only after the step that creates those files.

### Rule 2: never trust dirty output directories

Local `dist/`, `build/`, or generated-output directories can mask CI bugs.
Whenever CI validates artifacts, the workflow must clear the output directory or
build into an isolated location first.

### Rule 3: select the expected artifact precisely

Do not use broad globbing like `next(dist.glob('*.whl'))` when multiple versions
or multiple packages can exist. Match the current package name and version, then
assert that exactly one file matches.

### Rule 4: fail with a domain-specific error, not iterator noise

`StopIteration` is a garbage failure mode for CI diagnosis. Artifact-discovery
code must raise an assertion or exception that states which artifact pattern was
expected and what was actually found.

### Rule 5: test workflow intent, not YAML whitespace

Tests that validate CI workflows should assert command fragments and ordering,
not exact line wrapping or YAML folding. Otherwise harmless formatting changes
break the workflow tests while the actual workflow remains correct.

## Concrete anti-pattern

```python
wheel_path = next(DIST_DIR.glob('*.whl'))
```

Problems:

- may pick the wrong version
- may pick the wrong package in a multi-package repo
- crashes with `StopIteration`
- silently relies on stale local state

## Preferred pattern

```python
pattern = f'novitus_noviapi-{__version__}-*.whl'
matches = sorted(DIST_DIR.glob(pattern))
assert len(matches) == 1, matches
wheel_path = matches[0]
```

## Checklist for future agent work

Before changing CI or adding artifact tests, verify all of the following:

- Does the test depend on files that are created by an earlier workflow step?
- Is the output directory cleared before the build?
- Does the test look for the exact current artifact version?
- Will the failure message be understandable from CI logs alone?
- Could stale local files make the test pass even if CI ordering is wrong?
