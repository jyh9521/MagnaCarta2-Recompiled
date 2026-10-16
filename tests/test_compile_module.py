import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from tools.research import compile_module as module


class ModuleBuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.generated = self.root / 'generated'
        self.sdk = self.root / 'sdk'
        self.generated.mkdir()
        (self.sdk / 'include').mkdir(parents=True)
        (self.sdk / 'include' / 'runtime.h').write_text('// fixture')
        (self.generated / 'a.cpp').write_text('// a')
        (self.generated / 'b.cpp').write_text('// b')
        self.compiler = self.root / 'compiler.exe'
        self.compiler.write_bytes(b'fixture compiler')
        self.output = self.root / 'output'
        self.hash = module.digest(self.compiler)

    def runner(self, command, **kwargs):
        Path(command[-1][3:]).write_bytes(b'COFF fixture')
        return subprocess.CompletedProcess(command, 0)

    def run_build(self, runner=None, **kwargs):
        with patch.object(module, 'CLANG_CL_SHA256', self.hash), patch.object(module.subprocess, 'run', runner or self.runner):
            return module.build(self.generated, self.sdk, self.compiler, self.output, dict(os.environ), **kwargs)

    def test_strict_fp_command(self):
        command=module.command(self.compiler,self.sdk,self.generated,self.generated/'a.cpp',self.output/'a.obj')
        self.assertIn('/fp:strict',command)
        self.assertNotIn('/fp:fast',command)

    def test_strict_fp_metadata(self):
        self.run_build()
        self.assertEqual(json.loads((self.output/'inputs.json').read_text())['floating_point_contract'],'strict')

    def test_all_units_and_logs(self):
        result = self.run_build(jobs=2)
        self.assertTrue(result['success'])
        self.assertEqual(result['attempted_tus'], 2)
        self.assertEqual(len(list((self.output / 'logs').glob('*.json'))), 2)
        self.assertEqual(json.loads((self.output / 'inputs.json').read_text())['expected_tus'], 2)
        self.assertFalse(result['linked_game'])

    def test_nonzero_retained_and_all_units_attempted(self):
        def fail(command, **kwargs):
            kwargs['stdout'].write('literal failure\n')
            return subprocess.CompletedProcess(command, 2)
        result = self.run_build(fail)
        self.assertEqual(result['failed_tus'], 2)
        self.assertFalse(result['success'])
        self.assertEqual((self.output / 'logs' / 'a.cpp.txt').read_text(), 'literal failure\n')

    def test_zero_without_object_is_failure(self):
        result = self.run_build(lambda command, **kwargs: subprocess.CompletedProcess(command, 0))
        self.assertFalse(result['success'])

    def test_timeout_recorded(self):
        def timeout(command, **kwargs):
            raise subprocess.TimeoutExpired(command, 1)
        result = self.run_build(timeout, timeout=1)
        self.assertEqual(result['records'][0]['exit_status'], 124)

    def test_existing_output_rejected(self):
        self.output.mkdir()
        (self.output / 'preserve').write_text('untouched')
        with self.assertRaises(FileExistsError):
            self.run_build()
        self.assertEqual((self.output / 'preserve').read_text(), 'untouched')

    def test_hash_mismatch_before_output(self):
        with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
            module.build(self.generated, self.sdk, self.compiler, self.output, {})
        self.assertFalse(self.output.exists())

    def test_input_change_detected(self):
        def mutate(command, **kwargs):
            (self.generated / 'a.cpp').write_text('// changed')
            return self.runner(command, **kwargs)
        result = self.run_build(mutate, jobs=1)
        self.assertFalse(result['inputs_unchanged'])
        self.assertFalse(result['success'])

    def test_output_inside_input_rejected(self):
        self.output = self.generated / 'output'
        with self.assertRaisesRegex(ValueError, 'outside input'):
            self.run_build()
        self.assertFalse(self.output.exists())

    def test_invalid_concurrency_and_empty_input(self):
        with self.assertRaises(ValueError):
            self.run_build(jobs=5)
        for path in self.generated.iterdir():
            path.unlink()
        with self.assertRaisesRegex(ValueError, 'no generated'):
            self.run_build()

    def test_inventory_order_and_content_identity(self):
        first = module.inventory(self.generated)
        self.assertEqual(first, module.inventory(self.generated))
        (self.generated / 'a.cpp').write_text('// new')
        self.assertNotEqual(first['tree_sha256'], module.inventory(self.generated)['tree_sha256'])

    def test_compile_command_preserves_runtime_flags(self):
        command = module.command(self.compiler, self.sdk, self.generated, self.generated / 'a.cpp', self.output / 'a.obj')
        for flag in ('/Brepro', '/EHa', '/arch:AVX2', '/MD', '/bigobj'):
            self.assertIn(flag, command)
        self.assertNotIn('/DREX_FATAL=', command)

    def test_generated_source_manifest_mismatch(self):
        (self.generated / 'sources.cmake').write_text('${CMAKE_CURRENT_LIST_DIR}/a.cpp\n')
        with self.assertRaisesRegex(ValueError, 'sources.cmake'):
            self.run_build()
        self.assertFalse(self.output.exists())

    def test_generated_source_manifest_complete(self):
        (self.generated / 'sources.cmake').write_text('${CMAKE_CURRENT_LIST_DIR}/a.cpp\n${CMAKE_CURRENT_LIST_DIR}/b.cpp\n')
        self.assertTrue(self.run_build()['success'])
