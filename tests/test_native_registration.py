"""Synthetic native-table and initializer fixtures; no game data required."""
import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from tools.research.native_registration import (
    BASE, GNATIVES, core_lookup_witness, generated_entries, main,
    map_declarations, native_names, recover_initializers, recover_tables,
)


class NativeRegistrationTests(unittest.TestCase):
    def fixture(self, prefix='U', terminate=True, target=True):
        image = bytearray(512)
        name = f'int{prefix}ObjectexecFoo'.encode('utf-16-be') + b'\0\0'
        image[64:64+len(name)] = name
        struct.pack_into('>II', image, 256, BASE+64, BASE+400 if target else 0)
        if not terminate:
            struct.pack_into('>II', image, 264, 3, 4)
        return image, {BASE+400}

    def declaration(self, package='Core.xxx'):
        return {'package': package, 'package_sha256': '0'*64, 'export': 1,
                'path': 'Object.Foo', 'native_index': 129,
                'function_flags': 0x400, 'is_native': True,
                'metadata_status': 'validated'}

    def initializer(self, index=29):
        # Synthetic buffer encodes the supported compiler ctor shape, using
        # invented source slot 0x82000200 and invented target 0x82000300.
        words = [0x3D608328,0x3D408325,0x390A0D80,0x814BB660,
                 0x2F0A0000,0x409A0028,0x39401000,0x39200001,
                 0x3CE08250,0x912BB660,0x3968FFFC,0x38E75980,
                 0x7D4903A6,0x94EB0004,0x4200FFFC,0x3D408250,
                 0x81680000|index*4,0x392A5980,0x7F0B4840,0x419A0020,
                 0x3D408200,0x3D208326,0x39600000|index,0x814A0200,
                 0x91693F1C,0x91480000|index*4,0x4E800020,0x3D608200,
                 0x816B0200,0x91680000|index*4,0x4E800020]
        image = bytearray(1024)
        struct.pack_into('>31I', image, 0, *words)
        struct.pack_into('>I', image, 512, BASE+768)
        return image, {BASE, BASE+768}

    def test_native_name(self):
        image, _ = self.fixture()
        self.assertEqual(native_names(image)[BASE+64]['function'], 'Foo')

    def test_suffix_inside_string_rejected(self):
        image = ('prefixintUObjectexecFoo\0').encode('utf-16-be')
        self.assertEqual(native_names(image), {})

    def test_odd_name_rejected(self):
        self.assertEqual(native_names(b'x'+('intUObjectexecFoo\0').encode('utf-16-be')), {})

    def test_unterminated_name_rejected(self):
        self.assertEqual(native_names('intUObjectexecFoo'.encode('utf-16-be')), {})

    def test_nonzero_prelude_requires_explicit_profile_start(self):
        image, _ = self.fixture()
        image[62:64] = b'AB'
        self.assertFalse(native_names(image))
        self.assertIn(BASE+64, native_names(image, allowed_starts=(BASE+64,)))

    def test_table_pair_and_terminator(self):
        image, entries = self.fixture()
        result = recover_tables(image, entries)
        self.assertEqual(len(result['tables']), 1)
        self.assertEqual(result['tables'][0]['terminator'], BASE+264)
        self.assertEqual(result['tables'][0]['records'][0]['implementation'], BASE+400)

    def test_table_requires_terminator(self):
        image, entries = self.fixture(terminate=False)
        result = recover_tables(image, entries)
        self.assertFalse(result['tables'])
        self.assertEqual(len(result['unaccepted_nonzero_pairs']), 1)

    def test_code_pointer_must_be_generated_entry(self):
        image, _ = self.fixture()
        self.assertFalse(recover_tables(image, {BASE+404})['tables'])

    def test_zero_slot_is_not_implementation(self):
        image, entries = self.fixture(target=False)
        result = recover_tables(image, entries)
        self.assertFalse(result['tables'])
        self.assertEqual(len(result['static_zero_slots']), 1)

    def test_map_exact_source_identifier(self):
        image, entries = self.fixture()
        recovered = recover_tables(image, entries)
        result = map_declarations({'functions':[self.declaration()]}, recovered['tables'], [])
        self.assertEqual(result[0]['status'], 'unique-static-name-entry')
        self.assertEqual(result[0]['package_identity_in_name_table'], 'absent-not-proven')
        self.assertEqual(result[0]['native_class_prefix_binding'], 'not-proven-by-UFunction')
        self.assertEqual(result[0]['runtime_registration'], 'not-executed')

    def test_duplicate_declaration_identity_rejected(self):
        d = self.declaration()
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            map_declarations({'functions':[d,d]}, [], [])

    def test_same_class_in_multiple_packages_is_ambiguous(self):
        image, entries = self.fixture()
        recovered = recover_tables(image, entries)
        result = map_declarations({'functions':[self.declaration(),self.declaration('Other.xxx')]}, recovered['tables'], [])
        self.assertEqual([d['status'] for d in result], ['ambiguous-declaration-class']*2)

    def test_mixed_class_prefixes_remain_ambiguous(self):
        image, entries = self.fixture()
        tables = recover_tables(image, entries)['tables']
        other = copy.deepcopy(tables[0]); other['records'][0]['class_prefix'] = 'A'
        result = map_declarations({'functions':[self.declaration()]}, tables+[other], [])
        self.assertEqual(result[0]['status'], 'ambiguous-native-class-prefix')

    def test_unvalidated_metadata_rejected(self):
        d = self.declaration(); d['metadata_status'] = 'error'
        with self.assertRaisesRegex(ValueError, 'metadata'):
            map_declarations({'functions':[d]}, [], [])

    def test_native_flag_required(self):
        d = self.declaration(); d['function_flags'] = 0
        with self.assertRaises(ValueError):
            map_declarations({'functions':[d]}, [], [])

    def test_missing_name_stays_unresolved(self):
        result = map_declarations({'functions':[self.declaration()]}, [], [])
        self.assertEqual(result[0]['status'], 'no-static-name-entry')

    def test_initializer_exact_template(self):
        image, entries = self.initializer()
        result = recover_initializers(image, entries)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['destination'], GNATIVES+29*4)
        self.assertEqual(result[0]['source_pointer_slot'], BASE+512)
        self.assertEqual(result[0]['implementation'], BASE+768)

    def test_initializer_modified_instruction_rejected(self):
        image, entries = self.initializer(); image[12] ^= 1
        self.assertEqual(recover_initializers(image, entries), [])

    def test_initializer_destination_must_match_index(self):
        image, entries = self.initializer(); struct.pack_into('>I', image, 25*4, 0x91480078)
        self.assertEqual(recover_initializers(image, entries), [])

    def test_initializer_duplicate_path_slot_must_agree(self):
        image, entries = self.initializer(); struct.pack_into('>I', image, 28*4, 0x816B0204)
        self.assertEqual(recover_initializers(image, entries), [])

    def test_initializer_target_requires_entry(self):
        image, entries = self.initializer(); entries.remove(BASE+768)
        self.assertEqual(recover_initializers(image, entries), [])

    def test_initializer_itself_requires_entry(self):
        image, entries = self.initializer(); entries.remove(BASE)
        self.assertEqual(recover_initializers(image, entries), [])

    def test_initializer_truncated_rejected(self):
        image, entries = self.initializer()
        self.assertEqual(recover_initializers(image[:120], entries), [])

    def test_initializer_index_out_of_range_rejected(self):
        image, entries = self.initializer(4096)
        self.assertEqual(recover_initializers(image, entries), [])

    def test_cli_empty_report_rejected_before_binary_decode(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); paths = [root/n for n in ('xex','loader','uf','register')]
            for p in paths: p.write_text('fixture', encoding='utf-8')
            paths[2].write_text('{"functions":[]}', encoding='utf-8')
            args = ['--xex',str(paths[0]),'--loader-source',str(paths[1]),'--ufunction-report',str(paths[2]),'--generated-register',str(paths[3]),'--output',str(root/'out')]
            import tools.research.native_registration as module
            with patch.object(module, 'REGISTER_SHA256', module.digest(paths[3].read_bytes())):
                with self.assertRaisesRegex(ValueError, 'UFunction report hash'):
                    main(args)
            self.assertFalse((root/'out').exists())

    def test_cli_generated_witness_hash_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); paths = [root/n for n in ('xex','loader','uf','register')]
            for p in paths: p.write_text('fixture', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'registration witness hash'):
                main(['--xex',str(paths[0]),'--loader-source',str(paths[1]),'--ufunction-report',str(paths[2]),'--generated-register',str(paths[3]),'--output',str(root/'out')])

    def test_cli_output_alias_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'input'; path.write_bytes(b'fixture')
            with self.assertRaisesRegex(ValueError, 'aliases'):
                main(['--xex',str(path),'--loader-source',str(path),'--ufunction-report',str(path),'--generated-register',str(path),'--output',str(path)])

    def test_generated_template_rejects_mismatched_symbol(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'register.cpp'
            path.write_text('registrar->SetFunction(0x82300000, sub_82300004);', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'template'):
                generated_entries(path)


if __name__ == '__main__':
    unittest.main()
