from __future__ import annotations

import hashlib
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = PROJECT_ROOT / 'contracts/openapi/dist.json'
MANIFEST_PATH = PROJECT_ROOT / 'contracts/openapi/manifest.json'

REQUIRED_PATHS = {
    '/api/v1',
    '/api/v1/token',
    '/api/v1/queue',
    '/api/v1/receipt',
    '/api/v1/receipt/{id}',
    '/api/v1/invoice',
    '/api/v1/invoice/{id}',
    '/api/v1/nf_printout',
    '/api/v1/nf_printout/{id}',
    '/api/v1/daily_report',
    '/api/v1/daily_report/{id}',
    '/api/v1/eft',
    '/api/v1/eft/{id}',
    '/api/v1/graphic',
    '/api/v1/graphic/{id}',
    '/api/v1/configuration',
    '/api/v1/configuration/{id}',
    '/api/v1/status',
    '/api/v1/status/{id}',
    '/api/v1/direct_io',
    '/api/v1/direct_io/{id}',
    '/api/v1/lock',
    '/api/v1/lock/{id}',
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def test_contract_snapshot_exists_and_is_valid_json() -> None:
    contract = _load_json(CONTRACT_PATH)

    assert contract['openapi'].startswith('3.')
    assert contract['info']['title'] == 'NoviApi'


def test_contract_snapshot_covers_required_paths() -> None:
    contract = _load_json(CONTRACT_PATH)

    assert REQUIRED_PATHS.issubset(contract['paths'])


def test_contract_manifest_matches_snapshot() -> None:
    contract_bytes = CONTRACT_PATH.read_bytes()
    contract = json.loads(contract_bytes)
    manifest = _load_json(MANIFEST_PATH)

    assert manifest['source_url'] == 'https://noviapi.novitus.pl/dist.json'
    assert manifest['sha256'] == hashlib.sha256(contract_bytes).hexdigest()
    assert manifest['version'] == contract['info']['version']
