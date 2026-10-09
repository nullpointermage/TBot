"""Offline tests for the documentation checker; no bot/game process is started."""
import pathlib
import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from unittest.mock import patch

import check_docs


class DocumentationChecks(unittest.TestCase):
    def test_paths_normalize_array_members_and_keep_empty_arrays(self):
        sample = {'Targets': [{'Galaxy': 1}, {'Galaxy': 2}], 'Exclude': [], 'Enabled': False}
        self.assertEqual(set(check_docs.leaves(sample)), {'Targets[].Galaxy', 'Exclude', 'Enabled'})

    def test_duplicate_headings_and_fenced_headings(self):
        text = '# Start here\n## Same `name`\n## Same `name`\n```sh\n# Not a heading\n```\n'
        self.assertEqual(check_docs.anchors(text), {'start-here', 'same-name', 'same-name-1'})

    def test_scalar_array_parent_covers_members_but_not_object_fields(self):
        entries = [{'path': 'Names', 'type': 'array'}, {'path': 'Targets', 'type': 'array'}]
        self.assertEqual(check_docs.missing_paths({'Names[]', 'Targets[].Galaxy'}, entries),
                         ['Targets[].Galaxy'])

    def test_local_links_and_source_line_bounds(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            doc = root / 'README.md'
            doc.write_text('# Start\n')
            source = root / 'sample.cs'
            source.write_text('class Example {}\n')
            failures = []
            with patch.object(check_docs, 'ROOT', root):
                check_docs.check_links(doc, '[a](#start) [b](sample.cs#L1)', failures)
                self.assertEqual(failures, [])
                check_docs.check_links(doc, '[a](#missing) [b](sample.cs#L2) [c](absent.md)', failures)
            self.assertEqual(len(failures), 3)

    def test_external_links_are_not_network_probes(self):
        failures = []
        check_docs.check_links(check_docs.ROOT / 'README.md', '[site](https://example.invalid/path)', failures)
        self.assertEqual(failures, [])

    def test_incomplete_audit_fails_strict_and_is_visible_when_allowed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            reference = root / 'docs/reference'
            reference.mkdir(parents=True)
            (root / 'TBot').mkdir()
            for name in ['settings.json', 'instance_settings.json']:
                (root / 'TBot' / name).write_text('{"Enabled": false}')
            (root / 'README.md').write_text('# Enabled\n')
            (root / 'CONTRIBUTING.md').write_text('# Contributing\n')
            source = root / 'sample.cs'
            source.write_text('class Sample {}\n')
            (reference / 'settings-catalog.json').write_text(json.dumps([
                {'path': 'Enabled', 'type': 'bool', 'description': 'Example switch'}]))
            (reference / 'source-inventory.json').write_text(json.dumps([
                {'path': 'sample.cs', 'category': 'first-party', 'status': 'indexed',
                 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}]))
            for allow in [False, True]:
                stdout = io.StringIO()
                argv = ['check_docs'] + (['--allow-incomplete-audit'] if allow else [])
                with patch.object(check_docs, 'ROOT', root), patch.object(check_docs, 'REFERENCE', reference), patch('sys.argv', argv), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
                    failed = check_docs.main()
                result = json.loads(stdout.getvalue())
                self.assertEqual(failed, not allow)
                self.assertFalse(result['exhaustive_source_audit_complete'])
                self.assertEqual(result['incompletely_reviewed_first_party_files'], 1)


if __name__ == '__main__':
    unittest.main()
