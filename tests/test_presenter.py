"""Portable guards; real SDK/window execution is recorded by probe_presenter."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.research import probe_presenter as probe


GOOD = '''PRESENTER_SCOPE xex_loaded=0 guest_gpu_setup=0 game_assets=0
PRESENTER_PLUGIN abi=1 backend=any
PRESENTATION_CONTEXT initialized=1 ui_thread=1
PRESENTATION_SETUP status=00000000 has_presentation=1 presenter=1
PRESENTATION_WINDOW open=1 hidden=1 binding_requested=1
PRESENTATION_LOOP enter=1
PRESENTATION_LOOP exit=0
PRESENTATION_WINDOW_CLOSED closed=1 native_destroyed=1
PRESENTER_SHUTDOWN clean=1 loop_status=0
'''


class PresenterTests(unittest.TestCase):
    def test_complete(self):
        self.assertTrue(probe.validate_output(GOOD))

    def test_sdk_chatter_not_lifecycle(self):
        self.assertTrue(probe.validate_output('[gpu] device initialized\n' + GOOD))

    def test_every_marker_required(self):
        for line in GOOD.splitlines():
            with self.subTest(line=line), self.assertRaises(ValueError):
                probe.validate_output(GOOD.replace(line + '\n', ''))

    def test_no_duplicate_success(self):
        with self.assertRaises(ValueError):
            probe.validate_output(GOOD + GOOD.splitlines()[-1] + '\n')

    def test_order(self):
        with self.assertRaises(ValueError):
            probe.validate_output('\n'.join(reversed(GOOD.splitlines())))

    def test_visible_window_rejected(self):
        with self.assertRaises(ValueError):
            probe.validate_output(GOOD.replace('hidden=1', 'hidden=0'))

    def test_native_not_destroyed_rejected(self):
        with self.assertRaises(ValueError):
            probe.validate_output(GOOD.replace('native_destroyed=1', 'native_destroyed=0'))

    def test_timeout_rejected(self):
        with self.assertRaises(ValueError):
            probe.validate_output(GOOD + 'PRESENTER_PROCESS_TIMEOUT\n')

    def test_bounded_duration_before_platform(self):
        for duration in ('0', '99', '5001'):
            with self.subTest(duration=duration), self.assertRaisesRegex(ValueError, 'duration'):
                probe.main(['--sdk', 'unused', '--compiler', 'unused', '--vcvars', 'unused',
                            '--output', 'unused', '--duration-ms', duration])

    def test_command_no_title_or_codegen(self):
        with tempfile.TemporaryDirectory() as temp:
            command = probe.command(Path(temp)/'clang-cl.exe', Path(temp)/'sdk', Path(temp))
        self.assertIn('user32.lib', command)
        self.assertIn('rexruntime.lib', command)
        self.assertFalse(any('generated' in arg or 'title_probe.cpp' in arg for arg in command))

    def test_supported_dll_identity(self):
        with patch.object(probe, 'digest', side_effect=[probe.PLUGIN_SHA256, probe.RUNTIME_SHA256]):
            probe.verify_sdk_identity(Path('sdk'))

    def test_wrong_plugin_rejected_before_output(self):
        self.check_bad_identity('plugin')

    def test_wrong_runtime_rejected_before_output(self):
        self.check_bad_identity('runtime')

    def check_bad_identity(self, bad):
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'never-created'
            def identity(path):
                if Path(path).name=='compiler': return probe.CLANG_CL_SHA256
                if Path(path).name=='rexgpu-xenos.dll': return 'wrong' if bad=='plugin' else probe.PLUGIN_SHA256
                if Path(path).name=='rexruntime.dll': return 'wrong' if bad=='runtime' else probe.RUNTIME_SHA256
                raise AssertionError('unexpected read before DLL guards: '+str(path))
            with patch.object(probe, 'verify_host_compiler'), patch.object(probe, 'digest', side_effect=identity), patch.object(probe, 'run_record') as run:
                with self.assertRaisesRegex(ValueError, 'GPU/runtime identity'):
                    probe.main(['--sdk', str(Path(temp)/'sdk'), '--compiler', str(Path(temp)/'compiler'),
                                '--vcvars', str(Path(temp)/'vcvars'), '--output', str(output)])
                run.assert_not_called()
                self.assertFalse(output.exists())

    def test_os_failure_preserved(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(probe.subprocess, 'run', side_effect=OSError('test failure')):
            record = probe.run_record(['missing'], Path(temp), 'run', {}, 1)
            self.assertEqual(record['exit_status'], 127)
            self.assertIn('test failure', (Path(temp)/'run.txt').read_text())
            self.assertTrue((Path(temp)/'run.json').is_file())


if __name__ == '__main__':
    unittest.main()
