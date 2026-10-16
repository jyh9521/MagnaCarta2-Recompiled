import struct
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from tools.research import verify_callback as callback


def words(*values):return struct.pack('>'+str(len(values))+'I',*values)


class CallbackTests(unittest.TestCase):
    def code(self):
        # Synthetic values/registers, same narrow instruction vocabulary.
        return words(0x2B030000,0x4D9A0020,0x3CA08000,0x38C5FFFF,
                     0x90C30004,0x90A30000,0x90A30004,0x4E800020)

    def test_null_no_store_and_registers_unchanged(self):
        registers=list(range(32));registers[3]=0;memory=bytes(range(128))
        result=callback.execute_callback(self.code(),registers,memory)
        self.assertEqual(result['registers'],registers);self.assertEqual(result['memory'],memory)
        self.assertEqual(result['stores'],[]);self.assertTrue(result['equal'])

    def test_store_order_overwrite_and_big_endian(self):
        registers=list(range(32));registers[3]=32
        result=callback.execute_callback(self.code(),registers,bytes(128))
        self.assertEqual(result['stores'],[(36,0x7FFFFFFF),(32,0x80000000),(36,0x80000000)])
        self.assertEqual(result['memory'][32:40],bytes.fromhex('8000000080000000'))
        self.assertEqual(result['registers'][5],0xFFFFFFFF80000000)
        self.assertEqual(result['registers'][6],0xFFFFFFFF7FFFFFFF)
        self.assertFalse(result['equal'])

    def test_inputs_immutable(self):
        registers=list(range(32));registers[3]=32;memory=bytearray(128)
        callback.execute_callback(self.code(),registers,memory)
        self.assertEqual(memory,bytes(128));self.assertEqual(registers[5],5)

    def test_out_of_range_store(self):
        registers=[0]*32;registers[3]=126
        with self.assertRaisesRegex(ValueError,'outside fixture'):
            callback.execute_callback(self.code(),registers,bytes(128))

    def test_unknown_instruction_hard_fails(self):
        for word in (0,0x60000000,0x3CA18000):
            with self.assertRaisesRegex(ValueError,'unsupported'):
                callback.execute_callback(words(word,0x4E800020),[0]*32,bytes(8))

    def test_unaligned_missing_return_and_undefined_condition(self):
        for code in (b'',b'123',words(0x3CA08000),words(0x4D9A0020)):
            with self.assertRaises(ValueError):callback.execute_callback(code,[0]*32,bytes(8))

    def test_register_count_guard(self):
        with self.assertRaises(ValueError):callback.execute_callback(words(0x4E800020),[0]*31,bytes(8))

    def test_unsigned_compare_uses_low_word(self):
        registers=[0]*32;registers[3]=0x100000000
        self.assertTrue(callback.execute_callback(self.code(),registers,bytes(8))['equal'])

    def test_readonly_view_bounds(self):
        for address,size in ((0xFF,1),(0x100,-1),(0x103,2)):
            with self.assertRaises(ValueError):callback.view(bytes(4),address,size,0x100)

    def test_image_range_hash_guard(self):
        with patch.object(callback,'RANGES',{0x82000000:(4,'0'*64)}):
            with self.assertRaisesRegex(ValueError,'witness mismatch'):callback.verify_image(bytes(8))

    def test_missing_duplicate_and_fatal_generated_body_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with self.assertRaisesRegex(ValueError,'exactly one'):callback.extract_body(root)
            body='DEFINE_REX_FUNC(sub_8234FF10) {\n'+''.join('// test\n' for _ in range(12))+'REX_STORE_U32(0,0);'*3+'\n}'
            (root/'a.cpp').write_text(body);self.assertIn('body_sha256',callback.extract_body(root))
            (root/'b.cpp').write_text(body)
            with self.assertRaisesRegex(ValueError,'exactly one'):callback.extract_body(root)
            (root/'b.cpp').unlink();(root/'a.cpp').write_text(body.replace('// test','// REX_FATAL',1))
            with self.assertRaisesRegex(ValueError,'fatal/dispatch'):callback.extract_body(root)

    def test_incomplete_toolchain_rejected_before_source_read(self):
        with self.assertRaisesRegex(ValueError,'all toolchain'):
            callback.main(['--xex','missing','--loader-source','missing','--output','missing','--generated','missing'])

    def test_harness_cases_have_separate_local_scopes(self):
        cases=callback.fixtures(words(0x2B030000,0x4D9A0020,0x4E800020))
        text=callback.harness('/* fixture body */',cases)
        self.assertEqual(text.count('{ ctx=PPCContext{};'),5)
        self.assertEqual(text.count('failures+=!good; }'),5)
        self.assertIn('.u64==',text)


if __name__=='__main__':unittest.main()
