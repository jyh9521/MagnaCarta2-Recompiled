import hashlib
from pathlib import Path
import tempfile
import unittest
from tools.research import probe_generated_branches as probe


class GeneratedLeafProbeTests(unittest.TestCase):
    def fixture(self, root):
        path = Path(root) / 'fixture.cpp'
        path.write_text('prefix\nDEFINE_REX_FUNC(sub_82CE6748) {\n return;\n}\nDEFINE_REX_FUNC(sub_82DA3488) {\n return;\n}\n')
        return path

    def test_exact_bodies_and_boundaries(self):
        with tempfile.TemporaryDirectory() as root:
            path = self.fixture(root)
            result = probe.extract_bodies(root)
            first = result[0x82CE6748]
            self.assertEqual(first['source_sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual((first['body_start_line'], first['body_end_line']), (2, 4))
            self.assertEqual(first['body_sha256'], hashlib.sha256(first['body'].encode()).hexdigest())
            self.assertNotIn('prefix', first['body'])

    def test_duplicate_refused(self):
        with tempfile.TemporaryDirectory() as root:
            path = self.fixture(root)
            (Path(root) / 'copy.cpp').write_bytes(path.read_bytes())
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                probe.extract_bodies(root)

    def test_unresolved_refused(self):
        with tempfile.TemporaryDirectory() as root:
            path = self.fixture(root)
            path.write_text(path.read_text().replace('return;', 'REX_FATAL("fixture");', 1))
            with self.assertRaisesRegex(ValueError, 'unresolved'):
                probe.extract_bodies(root)

    def test_missing_refused(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, 'both'):
                probe.extract_bodies(root)

    def test_twenty_seven_oracle_fixtures(self):
        fixtures = probe.cases()
        self.assertEqual(len(fixtures), 27)
        self.assertEqual(sum(bool(f['expected_dispatch']) for f in fixtures), 1)
        self.assertEqual(fixtures[-1]['expected_dispatch'], 0x5000)
        self.assertEqual(fixtures[-1]['expected_return'], 0x3000)
        for fixture in fixtures[:24]:
            self.assertIn(fixture['expected_return'], (0, 1))

    def test_dispatch_replacement_is_explicit_and_only_boundary(self):
        with tempfile.TemporaryDirectory() as root:
            self.fixture(root)
            bodies = probe.extract_bodies(root)
            text = probe.harness_text(bodies, probe.cases())
            self.assertIn('#undef REX_CALL_INDIRECT_FUNC', text)
            self.assertIn('recorded_dispatch = (address)', text)
            self.assertNotIn('#undef REX_LOAD', text)
            for body in bodies.values():
                self.assertIn(body['body'], text)
