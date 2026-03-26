from __future__ import annotations

from noviapi._release_smoke import main


def test_release_smoke_main_runs_without_errors() -> None:
    main()
