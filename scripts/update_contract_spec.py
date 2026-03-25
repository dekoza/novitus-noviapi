from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import urlopen

SOURCE_URL = 'https://noviapi.novitus.pl/dist.json'


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Refresh the committed NoviAPI OpenAPI snapshot.',
    )
    parser.add_argument('--input', type=Path)
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('contracts/openapi/dist.json'),
    )
    parser.add_argument(
        '--manifest',
        type=Path,
        default=Path('contracts/openapi/manifest.json'),
    )
    parser.add_argument('--fetched-at')
    return parser.parse_args()


def _load_payload(input_path: Path | None) -> bytes:
    if input_path is not None:
        return input_path.read_bytes()
    with urlopen(SOURCE_URL, timeout=30) as response:
        return response.read()


def main() -> int:
    args = _parse_args()
    payload = _load_payload(args.input)
    try:
        contract = json.loads(payload)
    except json.JSONDecodeError as exc:
        print(f'Invalid OpenAPI document: {exc}', file=sys.stderr)
        return 1

    fetched_at = args.fetched_at or datetime.now(UTC).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    manifest = {
        'fetched_at': fetched_at,
        'info_title': contract['info']['title'],
        'sha256': hashlib.sha256(payload).hexdigest(),
        'source_url': SOURCE_URL,
        'version': contract['info']['version'],
    }
    args.manifest.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + '\n',
        encoding='utf-8',
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
