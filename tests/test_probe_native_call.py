import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools.research import probe_native_call as probe


class NativeProbeTests(unittest.TestCase):
    def output(self):
        return '\n'.join(['SETUP status=00000000', 'REGISTRATION count=58408 base=mapped',
                          *probe.expected_lines(), 'SHUTDOWN complete']) + '\n'

    def declaration(self):
        return {'functions': [{'package': 'Core.xxx', 'path': 'Object.Add_IntInt',
            'native_index': 146, 'is_native': True, 'package_sha256': 'package', 'payload_sha256': 'payload'}]}

    def test_eight_expected_cases_and_overflow(self):
        self.assertEqual(len(probe.CASES), 8)
        self.assertIn('result=80000000', probe.expected_lines()[5])
        self.assertIn('result=00000000', probe.expected_lines()[8])
        self.assertEqual(probe.validate_output(self.output()), probe.expected_lines())

    def test_wrong_result_rejected(self):
        with self.assertRaises(ValueError):
            probe.validate_output(self.output().replace('result=0000002A', 'result=0000002B'))

    def test_wrong_frame_or_cleanup_rejected(self):
        for before, after in [('code_advance=11', 'code_advance=10'), ('restored=1', 'restored=0'),
                              ('guards=1', 'guards=0'), ('fixture_released=1', 'fixture_released=0')]:
            with self.subTest(before=before), self.assertRaises(ValueError):
                probe.validate_output(self.output().replace(before, after))

    def test_missing_duplicate_case_rejected(self):
        for text in (self.output().replace(probe.expected_lines()[1] + '\n', ''),
                     self.output() + probe.expected_lines()[0] + '\n'):
            with self.assertRaises(ValueError):
                probe.validate_output(text)

    def test_missing_or_duplicate_lifecycle_rejected(self):
        for text in (self.output().replace('SHUTDOWN complete', ''), self.output() + 'SETUP status=00000000\n'):
            with self.assertRaises(ValueError):
                probe.validate_output(text)

    def test_runtime_dll_path_rejected(self):
        with self.assertRaises(ValueError):
            probe.validate_output(self.output() + 'RUNTIME_DLL /wrong/dll\n', '/expected/dll')

    def test_declaration_requires_unique_indexed_native(self):
        self.assertEqual(probe.declaration_evidence(self.declaration())['native_index'], 146)
        for key, value in [('native_index', 0), ('is_native', False), ('package', 'Engine.xxx')]:
            data = self.declaration(); data['functions'][0][key] = value
            with self.assertRaises(ValueError):
                probe.declaration_evidence(data)
        data = self.declaration(); data['functions'] *= 2
        with self.assertRaises(ValueError):
            probe.declaration_evidence(data)

    def image(self):
        image = bytearray(0x1320000)
        name = 'intUObjectexecAdd_IntInt'.encode('utf-16-be') + b'\0\0'
        image[0x157100:0x157100+len(name)] = name
        struct.pack_into('>II', image, 0x120F1E8, 0x82157100, probe.ADD_ADDRESS)
        for offset in (0x120B718, 0x120B728):
            struct.pack_into('>I', image, offset, probe.OPERAND_ADDRESS)
        struct.pack_into('>I', image, 0x120B828, probe.ADD_ADDRESS)
        return image

    def test_image_references_and_explicit_fixture_boundary(self):
        with patch.object(probe, 'OPERAND_SHA256', hashlib.sha256(bytes(64)).hexdigest()), patch.object(probe, 'INITIALIZERS', {0x82E707C8: (124, hashlib.sha256(bytes(124)).hexdigest())}):
            result = probe.native_evidence(self.image())
        self.assertIn('original initializer', result['token_binding'])
        self.assertEqual(result['implementation_address'], 0x8250BAF0)

    def test_image_name_pair_decoder_and_reference_guards(self):
        for offset in (0x157100, 0x120F1EF, 0x508E60, 0x120B728, 0x120B828, 0xE707C8):
            image = self.image(); image[offset] ^= 1
            with self.subTest(offset=offset), patch.object(probe, 'OPERAND_SHA256', hashlib.sha256(bytes(64)).hexdigest()), patch.object(probe, 'INITIALIZERS', {0x82E707C8: (124, hashlib.sha256(bytes(124)).hexdigest())}), self.assertRaises(ValueError):
                probe.native_evidence(image)

    def test_initializer_fill_guard_and_duplicate_output_rejected(self):
        for before, after in [('fallback_slots=4094', 'fallback_slots=4095'),
                              ('guard=1', 'guard=0'), ('duplicate_index=29', 'duplicate_index=0')]:
            with self.subTest(before=before), self.assertRaises(ValueError):
                probe.validate_output(self.output().replace(before, after))

    def host(self, directory):
        source = directory / 'probe.cpp'; source.write_text('fixture source')
        exe = directory / 'module_probe.exe'; exe.write_bytes(b'fixture binary')
        report = {'success': True, 'inputs_unchanged': True, 'object_count': 197,
                  'native_profile_generated_tree': probe.NATIVE_GENERATED_TREE,
                  'expected_mappings': 58408, 'module_probe.exe': {'sha256': probe.digest(exe)},
                  'records': [{'exit_status': 0}]}
        inputs = {'input_hashes': {str(source.resolve()): probe.digest(source)}}
        (directory / 'host-link.json').write_text(json.dumps(report))
        (directory / 'inputs.json').write_text(json.dumps(inputs))
        return source, exe, report

    def test_host_identity_and_full_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp); source, exe, report = self.host(directory)
            self.assertEqual(probe.verify_host(directory, source)[0], exe.resolve())
            report['object_count'] = 196
            (directory / 'host-link.json').write_text(json.dumps(report))
            with self.assertRaises(ValueError): probe.verify_host(directory, source)

    def test_host_modified_source_and_executable_rejected(self):
        for target in ('source', 'exe'):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp); source, exe, _ = self.host(directory)
                (source if target == 'source' else exe).write_bytes(b'changed')
                with self.assertRaises(ValueError): probe.verify_host(directory, source)

    def test_other_host_input_changed_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp); source, _, _ = self.host(directory)
            linker = directory / 'link.exe'; linker.write_bytes(b'linker')
            inputs = json.loads((directory / 'inputs.json').read_text())
            inputs['input_hashes'][str(linker)] = probe.digest(linker)
            (directory / 'inputs.json').write_text(json.dumps(inputs))
            linker.write_bytes(b'changed')
            with self.assertRaises(ValueError): probe.verify_host(directory, source)

    def test_sdk_changed_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp); source, _, _ = self.host(directory)
            sdk = directory / 'sdk'; sdk.mkdir(); (sdk / 'header.h').write_text('original')
            inputs = json.loads((directory / 'inputs.json').read_text())
            inputs['sdk'] = probe.inventory(sdk)
            inputs['generated'] = probe.inventory(sdk)
            inputs['compiler_resource_headers'] = probe.inventory(sdk)
            (directory / 'inputs.json').write_text(json.dumps(inputs))
            report = json.loads((directory / 'host-link.json').read_text())
            report['native_profile_generated_tree'] = inputs['generated']['tree_sha256']
            (directory / 'host-link.json').write_text(json.dumps(report))
            with patch.object(probe, 'NATIVE_GENERATED_TREE', inputs['generated']['tree_sha256']):
                probe.verify_host(directory, source, sdk)
                (sdk / 'header.h').write_text('changed')
                with self.assertRaises(ValueError): probe.verify_host(directory, source, sdk)

    def test_timeout_and_launch_failure_preserve_log(self):
        errors = [(subprocess.TimeoutExpired(['host'], 120, output=b'partial'), 124),
                  (OSError('launch failure'), 127)]
        for error, expected in errors:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as tmp:
                with patch.object(probe.subprocess, 'run', side_effect=error):
                    status, stdout, stderr = probe.run_host(['host'], Path(tmp), {})
                self.assertEqual(status, expected)
                self.assertTrue((Path(tmp) / 'run.txt').is_file())
                self.assertEqual((Path(tmp) / 'run.txt').read_text(), stdout + stderr)

    def test_source_keeps_original_dispatch_and_no_macro_replacement(self):
        source = Path('src/host/native_add_probe.cpp').read_text(encoding='utf-8')
        self.assertIn('Read32(base, kNatives + kAddIndex * 4)', source)
        self.assertIn('GetFunction(target)', source)
        self.assertNotIn('#define REX_', source)
        self.assertNotIn('DEFINE_REX_FUNC', source)
        self.assertNotIn('Write32(base, kNatives', source)
        self.assertIn('GetFunction(0x82E707C8)', source)
        self.assertIn('GetFunction(0x82E73108)', source)


if __name__ == '__main__':
    unittest.main()
