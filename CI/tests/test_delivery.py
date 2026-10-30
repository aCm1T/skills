"""Exercise the existing delivery helper with temporary synthetic archives."""

import importlib.util
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile


SCRIPT = Path(__file__).resolve().parents[2] / 'complete-coursework/scripts/verify_delivery.py'
spec = importlib.util.spec_from_file_location('verify_delivery', SCRIPT)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'answer.txt').write_text('synthetic answer\n', encoding='utf-8')

    def make_zip(self, member='answer.txt', content='synthetic answer\n'):
        with zipfile.ZipFile(self.root / 'source.zip', 'w') as archive:
            archive.writestr(member, content)

    def test_valid_archive_and_matching_source(self):
        self.make_zip()
        report = helper.run_checks(self.root, ['answer.txt'], ['source.zip'], [('source.zip', 'answer.txt', 'answer.txt')])
        self.assertTrue(report['passed'])
        self.assertTrue(report['matches'][0]['identical'])

    def test_modified_archive_member_fails(self):
        self.make_zip(content='different\n')
        self.assertFalse(helper.run_checks(self.root, [], [], [('source.zip', 'answer.txt', 'answer.txt')])['passed'])

    def test_missing_or_empty_file_fails(self):
        (self.root / 'empty.txt').touch()
        self.assertFalse(helper.run_checks(self.root, ['missing.txt', 'empty.txt'], [], [])['passed'])

    def test_traversal_and_symlink_rejected(self):
        self.make_zip(member='../escape.txt')
        self.assertFalse(helper.run_checks(self.root, [], ['source.zip'], [])['passed'])
        with zipfile.ZipFile(self.root / 'source.zip', 'w') as archive:
            info = zipfile.ZipInfo('link')
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, 'answer.txt')
        self.assertFalse(helper.run_checks(self.root, [], ['source.zip'], [])['passed'])

    def test_corrupt_zip_rejected(self):
        (self.root / 'source.zip').write_bytes(b'not a zip')
        self.assertFalse(helper.run_checks(self.root, [], ['source.zip'], [])['passed'])

    def test_outside_root_rejected(self):
        with self.assertRaises(ValueError):
            helper.local_path(self.root, '../outside.txt')

    def test_cli_refuses_to_overwrite_input_with_report(self):
        before = (self.root / 'answer.txt').read_bytes()
        result = subprocess.run([sys.executable, str(SCRIPT), '--root', str(self.root), '--file', 'answer.txt', '--report', 'answer.txt'], capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual((self.root / 'answer.txt').read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
