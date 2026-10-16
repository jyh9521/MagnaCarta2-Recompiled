from pathlib import Path
import tempfile
import unittest
from tools.maintenance.verify_workspace_move import verify


class WorkspaceMoveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.file = self.root / 'evidence.txt'
        self.file.write_bytes(b'original research')
        st = self.file.stat()
        self.manifest = {'evidence.txt': [st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns]}

    def test_identity(self):
        self.assertEqual(verify(self.root, self.manifest)['status'], 'PASS')

    def test_alias_identity(self):
        self.assertTrue(verify(self.root, self.manifest, self.root)['alias_verified'])

    def test_wrong_alias(self):
        other = self.root / 'other'; other.mkdir()
        with self.assertRaises(ValueError): verify(self.root, self.manifest, other)

    def test_changed_file(self):
        self.file.write_bytes(b'changed')
        with self.assertRaises(ValueError): verify(self.root, self.manifest)

    def test_missing(self):
        self.file.unlink()
        with self.assertRaises(FileNotFoundError): verify(self.root, self.manifest)

    def test_escape(self):
        for path in ['../escape', '/absolute', 'C:/absolute', 'a\\b', '']:
            with self.subTest(path=path), self.assertRaises(ValueError):
                verify(self.root, {path: next(iter(self.manifest.values()))})

    def test_malformed(self):
        for identity in [[], [1, 2, 3], [1, 2, 3, '4'], [True, 2, 3, 4]]:
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                verify(self.root, {'evidence.txt': identity})

    def test_empty_manifest(self):
        with self.assertRaises(ValueError): verify(self.root, {})
