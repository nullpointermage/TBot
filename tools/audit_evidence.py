"""Validate resumed audit attestations without equating indexing with review.

A complete range ledger is a checkable attestation, not proof of cognition;
parents must still independently sample the review's substantive findings.
"""
from __future__ import annotations

import hashlib
import json
import pathlib


def _inside(root, relative):
    if not isinstance(relative, str) or not relative or pathlib.Path(relative).is_absolute():
        raise ValueError('path must be repository-relative')
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError('path escapes repository')
    return path


def _complete_ranges(ranges, lines):
    if not isinstance(ranges, list):
        return False
    for pair in ranges:
        if not isinstance(pair, list) or len(pair) != 2:
            return False
        first, last = pair
        if type(first) is not int or type(last) is not int:
            return False
        if first < 1 or first > last or last > lines:
            return False
    cursor = 1
    for first, last in sorted(ranges):
        if first > cursor:
            return False
        cursor = max(cursor, last + 1)
    return cursor == lines + 1


def validate_read_evidence(root, entry):
    """Return errors for an explicit resumed attestation; leave legacy rows alone."""
    if 'read_evidence' not in entry:
        return []
    label = entry.get('path', '<missing source>')
    root = pathlib.Path(root).resolve()
    try:
        evidence = _inside(root, entry['read_evidence'])
        payload = json.loads(evidence.read_text(encoding='utf-8-sig'))
        if not isinstance(payload, dict) or not isinstance(payload.get('entries'), list):
            raise ValueError('evidence must contain an entries array')
        matches = [row for row in payload['entries']
                   if isinstance(row, dict) and row.get('path') == label]
        if len(matches) != 1:
            raise ValueError('source needs exactly one attestation')
        row = matches[0]
        source = _inside(root, label).read_bytes()
        digest = hashlib.sha256(source).hexdigest()
        lines = len(source.decode('utf-8-sig').splitlines())
        if row.get('status') != 'read':
            raise ValueError('attestation is not a complete read')
        if row.get('sha256') != digest or entry.get('sha256') != digest:
            raise ValueError('attestation/source hash mismatch')
        if type(row.get('lines')) is not int or row['lines'] != lines or entry.get('lines') != lines:
            raise ValueError('attestation/source line-count mismatch')
        if not isinstance(row.get('role'), str) or not row['role'].strip():
            raise ValueError('missing semantic role')
        notes = row.get('behavior_notes')
        if not isinstance(notes, list) or not notes or not all(isinstance(note, str) and note.strip() for note in notes):
            raise ValueError('missing semantic behavior notes')
        if not _complete_ranges(row.get('read_ranges'), lines):
            raise ValueError('read ranges are invalid or do not cover the whole file')
    except (OSError, ValueError, UnicodeError) as exc:
        return [f'Invalid read evidence for {label}: {exc}']
    return []
