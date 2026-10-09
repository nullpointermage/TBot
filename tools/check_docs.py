#!/usr/bin/env python3
"""Check handbook links, examples and source/settings reference coverage offline."""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parents[1]
REFERENCE = ROOT / 'docs/reference'


def leaves(value, path=''):
    if isinstance(value, dict) and value:
        for key, child in value.items():
            yield from leaves(child, f'{path}.{key}' if path else key)
    elif isinstance(value, list) and value:
        for child in value:
            yield from leaves(child, path + '[]')
    else:
        yield path


def outside_code(text):
    return re.sub(r'^(`{3,}|~{3,}).*?^\1\s*$', '', text, flags=re.M | re.S)


def missing_paths(expected, entries):
    keys = {entry['path'] for entry in entries}
    arrays = {entry['path'] for entry in entries
              if 'array' in entry.get('type', '').lower() or entry.get('type', '').endswith('[]')}
    return sorted(path for path in expected if path not in keys
                  and not (path.endswith('[]') and path[:-2] in arrays))


def anchors(text):
    seen = {}
    result = set(re.findall(r'<a\s+(?:[^>]*\s)?(?:id|name)=["\']([^"\']+)', text))
    for title in re.findall(r'^#{1,6}\s+(.+?)\s*#*\s*$', outside_code(text), re.M):
        title = re.sub(r'\[([^]]+)\]\([^)]*\)', r'\1', title)
        slug = re.sub(r'[^\w\- ]', '', title.lower()).replace(' ', '-')
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        result.add(slug + (f'-{count}' if count else ''))
    return result


def check_links(path, text, failures):
    for target in re.findall(r'(?<!!)\[[^]\n]*\]\(([^)\n]+)\)', outside_code(text)):
        if target.startswith('<') and target.endswith('>'):
            target = target[1:-1]
        else:
            target = target.split(' "', 1)[0]
        parsed = urllib.parse.urlsplit(target)
        if parsed.scheme or parsed.netloc:
            continue
        file = (path.parent / urllib.parse.unquote(parsed.path)).resolve() if parsed.path else path
        if not file.exists():
            failures.append(f'{path.relative_to(ROOT)}: missing local link {target}')
        elif parsed.fragment and file.suffix == '.md':
            fragment = urllib.parse.unquote(parsed.fragment)
            if fragment not in anchors(file.read_text(encoding='utf-8-sig')):
                failures.append(f'{path.relative_to(ROOT)}: missing heading {target}')
        elif parsed.fragment and re.fullmatch(r'L\d+(?:-L\d+)?', parsed.fragment) and file.is_file():
            line_numbers = [int(x) for x in re.findall(r'\d+', parsed.fragment)]
            if max(line_numbers) > len(file.read_text(encoding='utf-8-sig').splitlines()):
                failures.append(f'{path.relative_to(ROOT)}: source line outside file {target}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--links-only', action='store_true', help='Check prose links/JSON without reference indexes')
    parser.add_argument('--allow-incomplete-audit', action='store_true', help='Validate published artifacts while explicitly reporting incomplete semantic source review')
    args = parser.parse_args()
    failures = []
    paths = [ROOT / 'README.md', ROOT / 'CONTRIBUTING.md', *sorted((ROOT / 'docs').rglob('*.md'))]
    texts = {}
    snippets = 0
    for path in paths:
        text = path.read_text(encoding='utf-8-sig')
        texts[path] = text
        check_links(path, text, failures)
        for block in re.findall(r'^```json\s*\n(.*?)^```\s*$', text, flags=re.M | re.S):
            snippets += 1
            try:
                json.loads(block)
            except json.JSONDecodeError as exc:
                failures.append(f'{path.relative_to(ROOT)}: invalid fenced JSON: {exc}')
    summary = {'markdown_files': len(paths), 'json_snippets': snippets}
    if not args.links_only:
        config_files = [ROOT / 'TBot/settings.json', ROOT / 'TBot/instance_settings.json', *sorted((ROOT / 'TBot/profiles').glob('*.json'))]
        expected = set()
        for path in config_files:
            expected.update(leaves(json.loads(path.read_text(encoding='utf-8-sig'))))
        catalog_path = REFERENCE / 'settings-catalog.json'
        inventory_path = REFERENCE / 'source-inventory.json'
        for path in (catalog_path, inventory_path):
            if not path.exists():
                failures.append(f'Missing required reference {path.relative_to(ROOT)}')
        if catalog_path.exists():
            catalog = json.loads(catalog_path.read_text())
            entries = catalog if isinstance(catalog, list) else catalog['entries']
            keys = {entry['path'] for entry in entries}
            missing = missing_paths(expected, entries)
            if missing:
                failures.append('Undocumented template settings: ' + ', '.join(missing))
            prose = '\n'.join(texts.values())
            for entry in entries:
                if not entry.get('description') or not entry.get('type'):
                    failures.append('Missing description/type: ' + entry['path'])
                if entry['path'] not in prose:
                    failures.append('Setting absent from handbook prose: ' + entry['path'])
                for consumer in entry.get('consumers', []):
                    file = ROOT / consumer['file']
                    if not file.is_file():
                        failures.append('Missing consumer source: ' + consumer['file'])
                    elif consumer.get('symbol') and consumer['symbol'].split('.')[-1] not in file.read_text(encoding='utf-8-sig'):
                        failures.append('Unresolved consumer symbol: ' + str(consumer))
            summary.update(template_paths=len(expected), catalog_paths=len(keys), missing_template_paths=len(missing))
        if inventory_path.exists():
            index = json.loads(inventory_path.read_text())
            entries = index['entries'] if isinstance(index, dict) else index
            audited = 0
            incomplete = []
            for entry in entries:
                file = ROOT / entry['path']
                if not file.is_file():
                    failures.append('Missing inventoried source: ' + entry['path'])
                elif entry.get('check_hash', True) and hashlib.sha256(file.read_bytes()).hexdigest() != entry['sha256']:
                    failures.append('Source changed since audit: ' + entry['path'])
                if entry.get('status') == 'read':
                    audited += 1
                elif entry.get('category') == 'first-party':
                    incomplete.append(entry['path'])
                    if not args.allow_incomplete_audit:
                        failures.append('First-party source not fully audited: ' + entry['path'])
                for document in entry.get('documents', []):
                    if not (ROOT / document).is_file():
                        failures.append('Missing coverage document: ' + document)
            summary.update(inventoried_files=len(entries), read_files=audited,
                           incompletely_reviewed_first_party_files=len(incomplete),
                           exhaustive_source_audit_complete=not incomplete)
    summary.update(errors=len(failures))
    print(json.dumps(summary, indent=2))
    for failure in failures:
        print('ERROR ' + failure, file=sys.stderr)
    return bool(failures)


if __name__ == '__main__':
    raise SystemExit(main())
