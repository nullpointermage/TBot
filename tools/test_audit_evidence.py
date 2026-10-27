"""Regression tests for resumed source-read attestations; no game/network I/O."""
import hashlib
import json
import pathlib
import tempfile
import unittest

from audit_evidence import validate_read_evidence


class ReadEvidenceChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        source = b'first\nsecond\nthird\n'
        (self.root / 'sample.go').write_bytes(source)
        self.digest = hashlib.sha256(source).hexdigest()
        self.entry = {'path': 'sample.go', 'sha256': self.digest, 'lines': 3,
                      'status': 'read', 'read_evidence': 'audit.json'}

    def evidence(self, **changes):
        row = {'path': 'sample.go', 'sha256': self.digest, 'lines': 3,
               'read_ranges': [[1, 3]], 'status': 'read', 'role': 'Fixture',
               'behavior_notes': ['Three-line input fixture for this test.']}
        row.update(changes)
        (self.root / 'audit.json').write_text(json.dumps({'entries': [row]}))

    def test_full_coverage_and_overlapping_ranges_are_accepted(self):
        self.evidence(read_ranges=[[2, 3], [1, 2]])
        self.assertEqual(validate_read_evidence(self.root, self.entry), [])

    def test_gap_in_read_ranges_is_rejected(self):
        self.evidence(read_ranges=[[1, 1], [3, 3]])
        self.assertTrue(validate_read_evidence(self.root, self.entry))

    def test_out_of_bounds_and_invalid_ranges_are_rejected(self):
        for ranges in [[[0, 3]], [[1, 4]], [[3, 1]], [['1', 3]], [[True, 3]]]:
            with self.subTest(ranges=ranges):
                self.evidence(read_ranges=ranges)
                self.assertTrue(validate_read_evidence(self.root, self.entry))

    def test_stale_hash_or_line_count_is_rejected(self):
        for change in [{'sha256': '0' * 64}, {'lines': 4}]:
            with self.subTest(change=change):
                self.evidence(**change)
                self.assertTrue(validate_read_evidence(self.root, self.entry))

    def test_partial_and_missing_semantic_notes_are_rejected(self):
        for change in [{'status': 'partial'}, {'role': ''}, {'behavior_notes': []}]:
            with self.subTest(change=change):
                self.evidence(**change)
                self.assertTrue(validate_read_evidence(self.root, self.entry))

    def test_missing_duplicate_or_malformed_attestation_is_rejected(self):
        self.assertTrue(validate_read_evidence(self.root, self.entry))
        self.evidence()
        path = self.root / 'audit.json'
        data = json.loads(path.read_text())
        data['entries'] *= 2
        path.write_text(json.dumps(data))
        self.assertTrue(validate_read_evidence(self.root, self.entry))
        path.write_text('not json')
        self.assertTrue(validate_read_evidence(self.root, self.entry))

    def test_evidence_path_cannot_escape_repository(self):
        self.evidence()
        for path in ['../outside.json', '/outside.json']:
            with self.subTest(path=path):
                entry = dict(self.entry, read_evidence=path)
                self.assertTrue(validate_read_evidence(self.root, entry))

    def test_legacy_entries_without_new_attestations_are_unchanged(self):
        entry = dict(self.entry)
        entry.pop('read_evidence')
        self.assertEqual(validate_read_evidence(self.root, entry), [])


if __name__ == '__main__':
    unittest.main()
