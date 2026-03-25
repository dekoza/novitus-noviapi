from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = PROJECT_ROOT / 'scripts/update_contract_spec.py'


def test_update_contract_spec_writes_snapshot_and_manifest(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / 'source.json'
    output_path = tmp_path / 'dist.json'
    manifest_path = tmp_path / 'manifest.json'
    source_spec = {
        'openapi': '3.0.3',
        'info': {'title': 'NoviApi', 'version': '9.9.9'},
        'paths': {'/api/v1': {'get': {'responses': {'200': {}}}}},
    }
    source_path.write_text(json.dumps(source_spec), encoding='utf-8')

    subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            '--input',
            str(source_path),
            '--output',
            str(output_path),
            '--manifest',
            str(manifest_path),
            '--fetched-at',
            '2026-03-25T00:00:00+00:00',
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(output_path.read_text(encoding='utf-8')) == source_spec
    assert json.loads(manifest_path.read_text(encoding='utf-8')) == {
        'fetched_at': '2026-03-25T00:00:00+00:00',
        'info_title': 'NoviApi',
        'sha256': hashlib.sha256(
            source_path.read_bytes(),
        ).hexdigest(),
        'source_url': 'https://noviapi.novitus.pl/dist.json',
        'version': '9.9.9',
    }


def test_update_contract_spec_rejects_invalid_json(tmp_path: Path) -> None:
    source_path = tmp_path / 'source.json'
    output_path = tmp_path / 'dist.json'
    manifest_path = tmp_path / 'manifest.json'
    source_path.write_text('{', encoding='utf-8')

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            '--input',
            str(source_path),
            '--output',
            str(output_path),
            '--manifest',
            str(manifest_path),
            '--fetched-at',
            '2026-03-25T00:00:00+00:00',
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert 'Invalid OpenAPI document' in result.stderr
    assert not output_path.exists()
    assert not manifest_path.exists()
