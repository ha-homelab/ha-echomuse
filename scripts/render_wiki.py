#!/usr/bin/env python3
"""Export versioned public docs into build/wiki, without publishing or credentials."""
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
from urllib.parse import urlsplit

REPOSITORY = 'ha-homelab/ha-echomuse'
LINK = re.compile(r'(!?\[[^\]\n]*\]\()(<[^>]+>|[^\s)]+)([^\n)]*\))')


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(['git', '-C', str(root), *args], text=True)


def page_name(path: str) -> str:
    if path == 'README.md':
        return 'Home'
    if re.fullmatch(r'README\.[a-z]+\.md', path):
        return 'Home-' + path.split('.')[1]
    if path == 'docs/README.md':
        return 'Documentation'
    return path.removesuffix('.md').replace('/', '-')


def rewrite_outside_code(text: str, replace) -> str:
    """Rewrite prose links while leaving fenced and backtick examples intact."""
    def inline(chunk):
        runs = list(re.finditer(r'`+', chunk))
        # A code span closes only at a run with the same number of backticks.
        # Precompute matches so a large unmatched example stays linear.
        next_run, latest = {}, {}
        for i in range(len(runs) - 1, -1, -1):
            width = len(runs[i].group())
            if width in latest:
                next_run[i] = latest[width]
            latest[width] = i
        protected, i = [], 0
        while i < len(runs):
            run = runs[i]
            preceding = run.start() - 1
            while preceding >= 0 and chunk[preceding] == '\\':
                preceding -= 1
            escaped = (run.start() - preceding - 1) % 2
            if escaped or i not in next_run:
                i += 1
                continue
            closing = next_run[i]
            protected.append((run.start(), runs[closing].end()))
            i = closing + 1
        position = 0
        def replace_prose(match):
            nonlocal position
            while position < len(protected) and protected[position][1] <= match.start():
                position += 1
            if position < len(protected) and protected[position][0] <= match.start():
                return match.group(0)
            return replace(match)
        # A link can have a code-formatted label. Test where the link starts,
        # rather than splitting it at every protected span within its label.
        return LINK.sub(replace_prose, chunk)

    def flush():
        if pending:
            # Code spans can cross a line break, but not a blank paragraph.
            parts.extend(inline(part) for part in re.split(r'(\r?\n[ \t]*\r?\n)', ''.join(pending)))
            pending.clear()

    parts, pending, fence = [], [], None
    for line in text.splitlines(keepends=True):
        if fence:
            parts.append(line)
            marker, width = fence
            if re.fullmatch(r'[ \t]*' + re.escape(marker) + r'{' + str(width) + r',}[ \t]*(?:\r?\n)?', line):
                fence = None
            continue
        opening = re.match(r'^[ \t]*(`{3,}|~{3,})([^\r\n]*)', line)
        if opening and (opening[1][0] == '~' or '`' not in opening[2]):
            flush()
            fence = opening[1][0], len(opening[1])
            parts.append(line)
        else:
            pending.append(line)
    flush()
    return ''.join(parts)


def rewrite(text: str, source: str, pages: dict[str, str], ref: str) -> str:
    def replace(match):
        value = match.group(2).strip('<>')
        parsed = urlsplit(value)
        if parsed.scheme or parsed.netloc or not parsed.path:
            return match.group(0)
        pieces = []
        for part in (PurePosixPath(source).parent / parsed.path).parts:
            if part == '..':
                if not pieces:
                    raise ValueError('Documentation link leaves repository')
                pieces.pop()
            elif part != '.':
                pieces.append(part)
        target = '/'.join(pieces)
        suffix = ('?' + parsed.query if parsed.query else '') + ('#' + parsed.fragment if parsed.fragment else '')
        if target in pages and not match.group(1).startswith('!'):
            link = './' + pages[target]
        elif match.group(1).startswith('!'):
            link = f'https://raw.githubusercontent.com/{REPOSITORY}/{ref}/{target}'
        else:
            link = f'https://github.com/{REPOSITORY}/blob/{ref}/{target}'
        return match.group(1) + link + suffix + match.group(3)
    return rewrite_outside_code(text, replace)


def render(root: Path, ref: str) -> tuple[Path, int]:
    if not re.fullmatch(r'[0-9a-f]{40}', ref):
        raise ValueError('--ref must be a full lowercase commit SHA')
    # Both inventory and content come from the selected commit, never from an
    # uncommitted working file that may contain private or incomplete material.
    names = git(root, 'ls-tree', '-r', '--name-only', ref).splitlines()
    sources = [p for p in names if p.endswith('.md') and (
        p.startswith('docs/') or p in {'README.md', 'CONTRIBUTING.md', 'SECURITY.md'} or re.fullmatch(r'README\.[a-z]+\.md', p))]
    pages = {p: page_name(p) for p in sources}
    if len(set(pages.values())) != len(pages):
        raise ValueError('Duplicate generated wiki page name')
    output = root / 'build/wiki'
    if (root / 'build').is_symlink() or output.is_symlink():
        raise ValueError('Refusing symlink output directory')
    output.mkdir(parents=True, exist_ok=True)
    generated = {}
    for path, page in pages.items():
        content = git(root, 'show', f'{ref}:{path}')
        content = rewrite(content, path, pages, ref)
        content += f'\n\n---\nSource: [{path}](https://github.com/{REPOSITORY}/blob/{ref}/{path}) · revision `{ref[:12]}`. Edit the source repository, then regenerate this wiki.\n'
        generated[page + '.md'] = content
    generated['_Sidebar.md'] = '# EchoMuse documentation\n\n' + '\n'.join(
        f'- [{page}](./{page})' for page in pages.values()) + '\n'
    # Delete only files previously generated by this tool. Never delete unknown
    # pages from a wiki checkout; publishing is a separate reviewed operation.
    manifest = output / '.generated.json'
    if manifest.is_symlink():
        raise ValueError('Refusing symlink manifest')
    old = json.loads(manifest.read_text()) if manifest.exists() else {'files': []}
    for name in old['files']:
        if not re.fullmatch(r'[A-Za-z0-9_.-]+\.md', name):
            raise ValueError('Invalid prior manifest filename')
        previous = output / name
        if previous.is_symlink():
            raise ValueError('Refusing symlink generated page')
        if name not in generated:
            previous.unlink(missing_ok=True)
    for name, content in generated.items():
        destination = output / name
        if destination.is_symlink():
            raise ValueError('Refusing symlink generated page')
        destination.write_text(content)
    manifest.write_text(json.dumps({'source_ref': ref, 'files': sorted(generated)}, indent=2) + '\n')
    return output, len(generated)


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--ref', required=True, help='Full reviewed source commit SHA')
    args = cli.parse_args()
    output, count = render(Path(__file__).resolve().parents[1], args.ref)
    print(f'Exported {count} wiki pages to {output}; nothing was published.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
