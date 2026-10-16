#!/usr/bin/env python3
"""Stage generated pages in a clean wiki checkout; never commit or push."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

MANIFEST = '.source-manifest.json'
REMOTES = {'https://github.com/ha-homelab/ha-echomuse.wiki.git', 'git@github.com:ha-homelab/ha-echomuse.wiki.git'}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def page_path(root: Path, name: str) -> Path:
    if not re.fullmatch(r'[A-Za-z0-9_.-]+\.md', name):
        raise ValueError('Invalid managed wiki filename')
    path = root / name
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError('Managed wiki path is not a regular file')
    return path


def synchronize(source: Path, destination: Path, apply: bool = False) -> dict:
    source, destination = source.resolve(), destination.resolve()
    def git(*args):
        return subprocess.check_output(['git', '-C', str(destination), *args], text=True).strip()
    if Path(git('rev-parse', '--show-toplevel')).resolve() != destination:
        raise ValueError('Destination must be the root of the wiki checkout')
    if git('remote', 'get-url', 'origin') not in REMOTES:
        raise ValueError('Destination is not the expected EchoMuse wiki remote')
    if git('status', '--porcelain'):
        raise ValueError('Wiki checkout must be clean before synchronization')
    manifest_path = destination / MANIFEST
    if manifest_path.is_symlink():
        raise ValueError('Refusing a symlink manifest')
    generated = json.loads((source / '.generated.json').read_text())
    if not re.fullmatch(r'[0-9a-f]{40}', generated['source_ref']):
        raise ValueError('Invalid source revision')
    incoming = {name: page_path(source, name).read_bytes() for name in generated['files']}
    if len(incoming) != len(generated['files']):
        raise ValueError('Duplicate incoming filename')
    previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else {'files': {}}
    hashes = previous['files']
    if not isinstance(hashes, dict):
        raise ValueError('Invalid ownership manifest')
    # A clean checkout may contain later manual edits to a previously generated
    # page. Refuse to overwrite/delete them unless the recorded hash still matches.
    for name, expected in hashes.items():
        path = page_path(destination, name)
        if not isinstance(expected, str) or not re.fullmatch(r'[0-9a-f]{64}', expected):
            raise ValueError('Invalid ownership hash')
        if not path.is_file() or digest(path.read_bytes()) != expected:
            raise ValueError(f'Managed page changed outside the exporter: {name}')
    for name, data in incoming.items():
        path = page_path(destination, name)
        if name not in hashes and path.exists() and path.read_bytes() != data:
            raise ValueError(f'Existing unowned page would be overwritten: {name}')
    removed = sorted(set(hashes) - set(incoming))
    changed = sorted(name for name, data in incoming.items()
                     if not (destination / name).exists() or (destination / name).read_bytes() != data)
    result = {'source_ref': generated['source_ref'], 'write': changed, 'remove': removed, 'applied': apply}
    if apply:
        for name in removed:
            (destination / name).unlink()
        for name in changed:
            (destination / name).write_bytes(incoming[name])
        manifest_path.write_text(json.dumps({'source_ref': generated['source_ref'],
            'files': {name: digest(data) for name, data in sorted(incoming.items())}}, indent=2) + '\n')
    return result


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--wiki-checkout', type=Path, required=True)
    cli.add_argument('--apply', action='store_true', help='Write reviewed changes locally; no commit or push')
    args = cli.parse_args()
    source = Path(__file__).resolve().parents[1] / 'build/wiki'
    print(json.dumps(synchronize(source, args.wiki_checkout, args.apply), indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
