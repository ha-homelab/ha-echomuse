#!/usr/bin/env python3
"""Check public Markdown links, README coverage and accessible inert SVG files."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import unicodedata
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

LINK = re.compile(r'!?\[[^\]\n]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^"\n]*")?\)')
REFERENCE = re.compile(r'^\s*\[[^\]]+\]:\s*(\S+)', re.M)


def prose(text: str) -> str:
    """Exclude fenced examples; their paths are not documentation links."""
    lines, fence = [], None
    for line in text.splitlines():
        match = re.match(r'^\s*(`{3,}|~{3,})', line)
        if match:
            marker = match.group(1)
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None
            continue
        if fence is None:
            lines.append(line)
    return '\n'.join(lines)


def destinations(text: str) -> list[str]:
    text = prose(text)
    return [m.group(1).strip('<>') for m in LINK.finditer(text)] + REFERENCE.findall(text)


def anchors(text: str) -> set[str]:
    found, counts = set(), {}
    for line in prose(text).splitlines():
        match = re.match(r'^#{1,6}\s+(.+?)\s*#*$', line)
        if not match:
            continue
        label = re.sub(r'<[^>]+>', '', match.group(1)).lower()
        label = re.sub(r'!?\[([^]]+)\]\([^)]*\)', r'\1', label)
        label = ''.join(c for c in label if c in '-_ ' or unicodedata.category(c)[0] in 'LN')
        label = label.replace(' ', '-')
        count = counts.get(label, 0)
        counts[label] = count + 1
        found.add(label + (f'-{count}' if count else ''))
    found.update(re.findall(r'\b(?:id|name)=["\']([^"\']+)["\']', text))
    return found


def check_link(root: Path, source: Path, destination: str) -> str | None:
    url = urlsplit(destination)
    if url.scheme or url.netloc:
        if url.scheme in {'javascript', 'data', 'file'}:
            return 'unsafe link scheme'
        return None
    target = (source.parent / unquote(url.path)).resolve() if url.path else source
    if not target.is_relative_to(root.resolve()):
        return 'link leaves repository'
    if not target.exists():
        return 'missing target'
    if url.fragment and target.suffix == '.md' and unquote(url.fragment) not in anchors(target.read_text()):
        return 'missing Markdown anchor'
    return None


def check_svg(path: Path) -> list[str]:
    errors = []
    try:
        # The default ElementTree parser silently discards processing
        # instructions, including external xml-stylesheet resources.
        with path.open('rb') as stream:
            parsed = ET.iterparse(stream, events=('start', 'pi'))
            for event, _ in parsed:
                if event == 'pi':
                    errors.append('SVG contains processing instruction')
            root = parsed.root
    except ET.ParseError:
        return ['invalid SVG XML']
    if root.tag.split('}')[-1] != 'svg' or 'viewBox' not in root.attrib:
        errors.append('SVG needs a viewBox')
    for tag in ('title', 'desc'):
        if not any(e.tag.split('}')[-1] == tag and ''.join(e.itertext()).strip() for e in root):
            errors.append(f'SVG needs {tag}')
    for element in root.iter():
        if element.tag.split('}')[-1] in {'script', 'foreignObject', 'image'}:
            errors.append('SVG contains executable or embedded content')
        for name, value in element.attrib.items():
            local = name.split('}')[-1]
            if local.startswith('on') or (local == 'href' and not value.startswith('#')):
                errors.append('SVG contains event handler or external reference')
            if re.search(r'url\(\s*["\']?(?!#)[^\s"\')]', value, re.I):
                errors.append('SVG contains external URL')
        if element.tag.split('}')[-1] == 'style' and (
            re.search(r'@import', element.text or '', re.I)
            or re.search(r'url\(\s*["\']?(?!#)[^\s"\')]', element.text or '', re.I)
        ):
            errors.append('SVG style contains external resource syntax')
    return sorted(set(errors))


def check(root: Path) -> tuple[int, list[str]]:
    paths = subprocess.check_output(['git', '-C', str(root), 'ls-files', '--cached', '--others', '--exclude-standard', '-z']).decode().split('\0')
    docs = [root / p for p in sorted(set(paths)) if p.endswith(('.md', '.svg')) and (root / p).is_file()]
    errors = []
    for path in docs:
        if path.suffix == '.svg':
            errors += [f'{path.relative_to(root)}: {e}' for e in check_svg(path)]
        else:
            for url in destinations(path.read_text()):
                error = check_link(root, path, url)
                if error:
                    errors.append(f'{path.relative_to(root)}: {error}: {url}')
    inventory = json.loads((root / 'docs/languages.json').read_text())
    languages = inventory['languages']
    if inventory['canonical'] not in languages or len(languages) != len({x['readme'] for x in languages.values()}):
        errors.append('Invalid canonical or duplicate README in language inventory')
    navigation = {v['readme'] for v in languages.values()}
    for locale, value in languages.items():
        path = root / value['readme']
        if not path.is_file():
            errors.append(f'Missing README for {locale}')
            continue
        links = set(destinations(path.read_text()))
        for missing in sorted((navigation | set(inventory['required_readme_links'])) - links):
            errors.append(f'{value["readme"]}: missing required navigation: {missing}')
    return len(docs), sorted(set(errors))


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = cli.parse_args()
    count, errors = check(args.root.resolve())
    if errors:
        print('\n'.join(errors))
        return 1
    print(f'Documentation checks passed: {count} Markdown/SVG files; README language navigation complete.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
