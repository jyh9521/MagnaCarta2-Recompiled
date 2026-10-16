import struct
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from tools.research import verify_extended_native as extended


def code():return struct.pack('>11I',*extended.WORDS)


class ExtendedNativeTests(unittest.TestCase):
    def test_all256_suffixes_and_exact_cursor_delta(self):
        for suffix in range(256):
            case=extended.fixture(suffix);before=dict(case['memory']);regs=list(case['registers'])
            result=extended.execute(code(),regs,before,case['lr'])
            self.assertEqual(result['dispatch'],case['target']);self.assertEqual(result['ctr'],case['target'])
            self.assertEqual(result['lr'],case['lr']);self.assertEqual(result['registers'][8],suffix)
            self.assertEqual(result['registers'][6],suffix*4)
            self.assertEqual(result['registers'][7],0xFFFFFFFF83251180)
            self.assertEqual(result['registers'][10],0xFFFFFFFF83250D80)
            self.assertEqual(result['registers'][9],case['cursor']+1)
            self.assertEqual(result['registers'][11],case['target'])
            self.assertEqual(result['stores'],[{'address':case['frame']+12,'value':case['cursor']+1}])
            wanted=dict(before);extended.put_word(wanted,case['frame']+12,case['cursor']+1)
            self.assertEqual(result['memory'],wanted)
            self.assertEqual(case['memory'],before);self.assertEqual(case['registers'],regs)
            for index in set(range(32))-{6,7,8,9,10,11}:self.assertEqual(result['registers'][index],regs[index])

    def test_suffix_is_one_byte_and_not_bool(self):
        for value in (-1,256,True,'0'):
            with self.assertRaises(ValueError):extended.fixture(value)

    def test_each_unknown_word_is_rejected(self):
        for offset in range(0,44,4):
            blob=bytearray(code());blob[offset+3]^=1
            with self.assertRaisesRegex(ValueError,'unknown'):extended.execute(blob,[0]*32,{},7)

    def test_input_shape_guards(self):
        for blob,regs in ((b'',[]),(code()[:-1],[0]*32),(code(),[0]*31)):
            with self.assertRaises(ValueError):extended.execute(blob,regs,{},7)

    def test_missing_and_invalid_bytes_rejected(self):
        case=extended.fixture(0)
        for address in (case['frame']+12,case['cursor'],extended.TABLE):
            for replacement in (None,True,-1,256):
                memory=dict(case['memory'])
                if replacement is None:memory.pop(address)
                else:memory[address]=replacement
                with self.assertRaisesRegex(ValueError,'fixture'):extended.execute(code(),case['registers'],memory,7)

    def test_cursor_word_wrap_preserves_64bit_addi_result(self):
        case=extended.fixture(3);memory={0xFFFFFFFF:3};extended.put_word(memory,case['frame']+12,0xFFFFFFFF)
        extended.put_word(memory,extended.TABLE+12,0x81234567)
        result=extended.execute(code(),case['registers'],memory,7)
        self.assertEqual(result['registers'][9],0x100000000)
        self.assertEqual(result['stores'][0]['value'],0)
        self.assertEqual(result['dispatch'],0x81234567)

    def test_original_hash_guard(self):
        with patch.object(extended,'RANGES',{0x82000000:(4,'0'*64)}):
            with self.assertRaisesRegex(ValueError,'witness mismatch'):extended.verify_original(bytes(8))

    def body(self):return 'DEFINE_REX_FUNC(sub_82517D70) {\nREX_STORE_U32(0,0); REX_CALL_INDIRECT_FUNC(0);\n}'

    def test_unique_body_and_exact_metadata_required(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with self.assertRaises(ValueError):extended.extract_body(root)
            (root/'a.cpp').write_text(self.body());(root/'mc2_probe_init.cpp').write_text('{ 0x82517D70, sub_82517D70 },')
            register=root/'mc2_probe_register.cpp';register.write_text('')
            with self.assertRaisesRegex(ValueError,'one-to-one'):extended.extract_body(root)
            good='registrar->SetFunction(0x82517D70, sub_82517D70);';register.write_text(good)
            self.assertTrue(extended.extract_body(root)['registered'])
            for bad in (good*2,good.replace('sub_82517D70','wrong')):
                register.write_text(bad)
                with self.assertRaises(ValueError):extended.extract_body(root)
            register.write_text(good);(root/'b.cpp').write_text(self.body())
            with self.assertRaises(ValueError):extended.extract_body(root)

    def test_fatal_and_wrong_store_count_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for body in ('REX_FATAL();','return;','REX_STORE_U32(0,0);'*2+'REX_CALL_INDIRECT_FUNC(0);'):
                (root/'a.cpp').write_text('DEFINE_REX_FUNC(sub_82517D70) {\n'+body+'\n}')
                with self.assertRaises(ValueError):extended.extract_body(root)

    def test_harness_uses_original_memory_macros_and_host_page_offset(self):
        text=extended.harness('/* synthetic body */',code())
        self.assertIn('REX_PHYS_HOST_OFFSET(guest_pages[i])',text)
        self.assertIn('suffix<256',text);self.assertIn('expected_regs[256][32]',text)
        self.assertIn('before[suffix%2?3:0][12+i]',text)
        self.assertIn('VirtualFree(base,0,MEM_RELEASE)',text)
        self.assertNotIn('LoadXexImage',text)
        self.assertIn('#define REX_CALL_INDIRECT_FUNC(address) do { recorded=(address); }',text)

    def test_incomplete_bundle_rejected_before_input_reads(self):
        with self.assertRaisesRegex(ValueError,'all toolchain'):
            extended.main(['--xex','missing','--loader-source','missing','--mapping','missing','--output','missing','--sdk','missing'])


if __name__=='__main__':unittest.main()
