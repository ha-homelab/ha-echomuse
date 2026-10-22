#!/usr/bin/env python3
"""Check pinned EchoMuse source and build a separate Bluetooth-auth overlay.

No network access, source edits, database access, or service restarts occur.
Without --output this only checks. Custom API files require an explicit reviewed
SHA-256 and an unchanged original key-handler function.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / 'patches/echomuse-2.26.0/manifest.json'
DIGEST = re.compile(r'[0-9a-f]{64}\Z')
HUNK = re.compile(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@')
MAX_SOURCE_BYTES = 2 * 1024 * 1024


class PatchError(ValueError):
    """The source or patch differs from the reviewed inputs."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_relative(value: str) -> str:
    path = PurePosixPath(value)
    if (not value or path.is_absolute() or '..' in path.parts or '\\' in value
            or str(path) != value):
        raise PatchError('Unsafe relative file path')
    return value


def read_regular(root: Path, relative: str) -> bytes:
    relative = safe_relative(relative)
    current = root
    for part in PurePosixPath(relative).parts:
        current = current / part
        if current.is_symlink():
            raise PatchError(f'Symlink refused: {relative}')
    if not current.is_file() or current.stat().st_size > MAX_SOURCE_BYTES:
        raise PatchError(f'Missing or oversized source: {relative}')
    return current.read_bytes()


def parse_patch(text: str) -> dict[str, list[dict]]:
    """Parse this package's unified text diffs, without invoking patch/fuzz."""
    lines = text.splitlines(keepends=True)
    result = {}
    i = 0
    while i < len(lines):
        if not lines[i].startswith('--- a/'):
            raise PatchError('Unexpected patch header')
        name = safe_relative(lines[i][6:].rstrip('\n'))
        if name in result or i + 1 >= len(lines) or lines[i + 1] != f'+++ b/{name}\n':
            raise PatchError('Duplicate or mismatched patch file')
        i += 2
        hunks = []
        while i < len(lines) and not lines[i].startswith('--- a/'):
            match = HUNK.match(lines[i])
            if not match:
                raise PatchError(f'Invalid hunk header: {name}')
            start = int(match[1])
            old_count = int(match[2] or 1)
            new_count = int(match[4] or 1)
            i += 1
            before, after = [], []
            while i < len(lines) and not lines[i].startswith(('@@ ', '--- a/')):
                line = lines[i]
                if line[0] not in ' +-':
                    raise PatchError('Unsupported patch line')
                if line[0] in ' -':
                    before.append(line[1:])
                if line[0] in ' +':
                    after.append(line[1:])
                i += 1
            if len(before) != old_count or len(after) != new_count:
                raise PatchError(f'Hunk line-count mismatch: {name}')
            hunks.append({'start': start, 'before': before, 'after': after})
        if not hunks:
            raise PatchError('Empty file diff')
        result[name] = hunks
    return result


def function_region(source: str, name: str) -> tuple[int, int, str]:
    lines = source.splitlines(keepends=True)
    nodes = [n for n in ast.parse(source).body
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]
    if len(nodes) != 1:
        raise PatchError('Expected one top-level API key handler')
    node = nodes[0]
    first = min([node.lineno] + [d.lineno for d in node.decorator_list]) - 1
    last = node.end_lineno
    return first, last, ''.join(lines[first:last])


def apply_exact(source: str, hunks: list[dict]) -> str:
    lines = source.splitlines(keepends=True)
    result, cursor = [], 0
    for hunk in hunks:
        start = hunk['start'] - 1 if hunk['before'] else hunk['start']
        before = hunk['before']
        if start < cursor or lines[start:start + len(before)] != before:
            raise PatchError('Patch context differs; no fuzz or offset accepted')
        result.extend(lines[cursor:start])
        result.extend(hunk['after'])
        cursor = start + len(before)
    result.extend(lines[cursor:])
    return ''.join(result)


def apply_custom_api(source: str, hunks: list[dict], spec: dict) -> str:
    first, last, region = function_region(source, spec['function'])
    digest = sha256(region.encode())
    if digest == spec['after_function_sha256']:
        return source
    if digest != spec['before_function_sha256']:
        raise PatchError('Custom API key handler differs from reviewed upstream function')
    for hunk in hunks:
        before_lines, after_lines = list(hunk['before']), list(hunk['after'])
        # Unified diffs can include unchanged neighboring functions. Only
        # changed lines belong in the already hash-verified handler region.
        while before_lines and after_lines and before_lines[0] == after_lines[0]:
            before_lines.pop(0)
            after_lines.pop(0)
        while before_lines and after_lines and before_lines[-1] == after_lines[-1]:
            before_lines.pop()
            after_lines.pop()
        before, after = ''.join(before_lines), ''.join(after_lines)
        if not before or region.count(before) != 1:
            raise PatchError('Custom API hunk is not unique inside the key handler')
        region = region.replace(before, after, 1)
    if sha256(region.encode()) != spec['after_function_sha256']:
        raise PatchError('Custom API result differs from reviewed key handler')
    lines = source.splitlines(keepends=True)
    return ''.join(lines[:first]) + region + ''.join(lines[last:])


def prepare(source: Path, manifest_path: Path = DEFAULT_MANIFEST,
            reviewed_custom_api_sha256: str | None = None) -> tuple[dict, dict[str, bytes]]:
    source = Path(source)
    if source.is_symlink() or not source.is_dir():
        raise PatchError('Source must be a regular directory')
    manifest = json.loads(Path(manifest_path).read_text())
    if manifest.get('schema') != 1:
        raise PatchError('Unsupported manifest schema')
    patch_data = read_regular(Path(manifest_path).parent, manifest['patch'])
    if sha256(patch_data) != manifest['patch_sha256']:
        raise PatchError('Packaged patch SHA-256 differs from manifest')
    hunks = parse_patch(patch_data.decode('utf-8'))
    if set(hunks) != set(manifest['files']):
        raise PatchError('Patch file inventory differs from manifest')
    if reviewed_custom_api_sha256 is not None and not DIGEST.fullmatch(reviewed_custom_api_sha256):
        raise PatchError('Reviewed custom API SHA-256 must be 64 lowercase hex digits')
    custom_spec = manifest['custom_api']
    result, entries = {}, {}
    for name, hashes in manifest['files'].items():
        if not all(DIGEST.fullmatch(hashes[k]) for k in ('before_sha256', 'after_sha256')):
            raise PatchError('Malformed source hash in manifest')
        raw = read_regular(source, name)
        before_hash = sha256(raw)
        text = raw.decode('utf-8')
        custom = False
        if before_hash == hashes['after_sha256']:
            patched = text
        elif before_hash == hashes['before_sha256']:
            patched = apply_exact(text, hunks[name])
        elif name == custom_spec['path'] and before_hash == reviewed_custom_api_sha256:
            custom = True
            patched = apply_custom_api(text, hunks[name], custom_spec)
        else:
            raise PatchError(f'Source SHA-256 differs: {name}')
        data = patched.encode('utf-8')
        if not custom and sha256(data) != hashes['after_sha256']:
            raise PatchError(f'Patched SHA-256 differs: {name}')
        if name.endswith('.py'):
            ast.parse(patched)
        result[name] = data
        entries[name] = {'input_sha256': before_hash, 'output_sha256': sha256(data),
                         'reviewed_custom_api': custom}
    receipt = {'schema': 1, 'upstream': manifest['upstream'],
               'patch_sha256': manifest['patch_sha256'], 'files': entries}
    return receipt, result


def compile_dashboard(receipt: dict, files: dict[str, bytes], esbuild: Path) -> None:
    """Compile the served JavaScript with upstream's exact esbuild version/flags."""
    executable = str(Path(esbuild).resolve())
    version = subprocess.run([executable, '--version'], capture_output=True,
                             text=True, check=True, timeout=10).stdout.strip()
    if version != '0.20.2':
        raise PatchError('Dashboard compiler must be esbuild 0.20.2')
    with tempfile.TemporaryDirectory(prefix='echomuse-dashboard-') as directory:
        source, target = Path(directory) / 'dashboard.jsx', Path(directory) / 'dashboard.js'
        source.write_bytes(files['controller/static/dashboard.jsx'])
        subprocess.run([executable, str(source), '--bundle=false', '--jsx=transform',
                        '--jsx-factory=React.createElement', '--jsx-fragment=React.Fragment',
                        '--outfile=' + str(target)], check=True, capture_output=True, timeout=30)
        data = target.read_bytes()
        if not data or len(data) > MAX_SOURCE_BYTES:
            raise PatchError('Missing or oversized compiled dashboard')
        data.decode('utf-8')
    name = 'controller/static/dashboard.js'
    files[name] = data
    receipt['files'][name] = {'output_sha256': sha256(data), 'generated': True}
    receipt['dashboard_build'] = {
        'compiler': 'esbuild', 'version': version,
        'input_sha256': sha256(files['controller/static/dashboard.jsx']),
        'output_sha256': sha256(data),
    }


def write_overlay(output: Path, receipt: dict, files: dict[str, bytes]) -> None:
    """Create a new private output directory; never overwrite source or outputs."""
    output = Path(output)
    # All validation has completed before an output directory is created.
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    for name, data in files.items():
        target = output / safe_relative(name)
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with target.open('xb') as stream:
            os.chmod(target, 0o600)
            stream.write(data)
    # The receipt is written last: its absence identifies an incomplete output.
    with (output / 'patch-receipt.json').open('x') as stream:
        os.chmod(output / 'patch-receipt.json', 0o600)
        json.dump(receipt, stream, indent=2)
        stream.write('\n')


def main(argv=None) -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--source', required=True, type=Path, help='extracted upstream tree or private source copy')
    cli.add_argument('--output', type=Path, help='new overlay directory; omit for read-only check')
    cli.add_argument('--esbuild', type=Path, help='esbuild 0.20.2 executable; required with --output')
    cli.add_argument('--reviewed-custom-api-sha256', help='explicit SHA-256 of a manually reviewed custom em_api.py')
    args = cli.parse_args(argv)
    try:
        if args.output and not args.esbuild:
            raise PatchError('--output requires --esbuild to build the served dashboard.js')
        receipt, files = prepare(args.source, reviewed_custom_api_sha256=args.reviewed_custom_api_sha256)
        if args.esbuild:
            compile_dashboard(receipt, files, args.esbuild)
        if args.output:
            write_overlay(args.output, receipt, files)
        print(json.dumps({'mode': 'overlay-created' if args.output else 'check-only',
                          'patch_sha256': receipt['patch_sha256'], 'files': receipt['files']}, indent=2))
        return 0
    except (PatchError, OSError, ValueError, KeyError, TypeError, SyntaxError,
            subprocess.SubprocessError) as error:
        # Never print source contents, exception payloads, keys, or tokens.
        print(f'Patch check failed ({type(error).__name__}); inputs left unchanged.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
