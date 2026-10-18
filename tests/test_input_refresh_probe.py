"""Contract checks and optional real-SDK serialized-control smoke tests.

MC2_INPUT_REFRESH_PROBE must name a separately hash-verified local probe EXE.
The optional checks do not establish race-freedom or game acceptance.
"""
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InputRefreshContractTests(unittest.TestCase):
    def test_real_sdk_calls_and_no_game_image(self):
        text = (ROOT / 'src/host/input_refresh_probe.cpp').read_text(encoding='utf-8')
        self.assertIn('input.GetState(0,&state)', text)
        self.assertIn('input.SetState(0,&vibration)', text)
        self.assertNotIn('LoadLibrary', text)
        self.assertNotIn('RefreshDevices()', text)  # SDK remains the implementation.

    def test_control_gate_covers_both_calls(self):
        text = (ROOT / 'src/host/input_refresh_probe.cpp').read_text(encoding='utf-8')
        self.assertIn('if(serial)mc2::host::input_call_gate::Invoke(get?1:2,call);else call();', text)
        self.assertIn('std::barrier ready(2)', text)
        self.assertIn('loops>100000', text)
        self.assertIn('length>16384', text)
        self.assertIn('EXCEPTION_CONTINUE_SEARCH', text)


@unittest.skipUnless(os.environ.get('MC2_INPUT_REFRESH_PROBE'), 'local SDK probe not configured')
class InputRefreshNativeTests(unittest.TestCase):
    def run_probe(self, *args):
        path = Path(os.environ['MC2_INPUT_REFRESH_PROBE']).resolve(strict=True)
        return subprocess.run([str(path), *args], capture_output=True, text=True, timeout=60)

    def test_serialized_large(self):
        result = self.run_probe('serialized', '10000', '8192')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('completed reads=10000 writes=10000 errors=0 mode=serialized', result.stdout)

    def test_serialized_short(self):
        result = self.run_probe('serialized', '10000', '32')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('completed reads=10000 writes=10000 errors=0 mode=serialized', result.stdout)

    def test_invalid_modes_and_bounds(self):
        for args in [('other', '1', '32'), ('serialized', '0', '32'),
                     ('serialized', '100001', '32'), ('serialized', '1', '16385')]:
            with self.subTest(args=args):
                self.assertEqual(self.run_probe(*args).returncode, 2)
